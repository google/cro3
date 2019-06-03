# -*- coding: utf-8 -*-
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Devserver module for handling update client requests."""

from __future__ import print_function

import collections
import json
import os
import subprocess
import threading
import time
import urlparse

import cherrypy

import build_util
import common_util
import devserver_constants as constants
import log_util

# TODO(crbug.com/872441): We try to import nebraska from different places
# because when we install the devserver, we copy the nebraska.py into the main
# directory. Once this bug is resolved, we can always import from nebraska
# directory.
try:
  from nebraska import nebraska
except ImportError:
  import nebraska


# If used by client in place of an pre-update version string, forces an update
# to the client regardless of the relative versions of the payload and client.
FORCED_UPDATE = 'ForcedUpdate'

# Module-local log function.
def _Log(message, *args):
  return log_util.LogWithTag('UPDATE', message, *args)


class AutoupdateError(Exception):
  """Exception classes used by this module."""
  pass


def _ChangeUrlPort(url, new_port):
  """Return the URL passed in with a different port"""
  scheme, netloc, path, query, fragment = urlparse.urlsplit(url)
  host_port = netloc.split(':')

  if len(host_port) == 1:
    host_port.append(new_port)
  else:
    host_port[1] = new_port

  print(host_port)
  netloc = '%s:%s' % tuple(host_port)

  return urlparse.urlunsplit((scheme, netloc, path, query, fragment))

def _NonePathJoin(*args):
  """os.path.join that filters None's from the argument list."""
  return os.path.join(*filter(None, args))


class HostInfo(object):
  """Records information about an individual host.

  Members:
    attrs: Static attributes (legacy)
    log: Complete log of recorded client entries
  """

  def __init__(self):
    # A dictionary of current attributes pertaining to the host.
    self.attrs = {}

    # A list of pairs consisting of a timestamp and a dictionary of recorded
    # attributes.
    self.log = []

  def __repr__(self):
    return 'attrs=%s, log=%s' % (self.attrs, self.log)

  def AddLogEntry(self, entry):
    """Append a new log entry."""
    # Append a timestamp.
    assert not 'timestamp' in entry, 'Oops, timestamp field already in use'
    entry['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
    # Add entry to hosts' message log.
    self.log.append(entry)


class HostInfoTable(object):
  """Records information about a set of hosts who engage in update activity.

  Members:
    table: Table of information on hosts.
  """

  def __init__(self):
    # A dictionary of host information. Keys are normally IP addresses.
    self.table = {}

  def __repr__(self):
    return '%s' % self.table

  def GetInitHostInfo(self, host_id):
    """Return a host's info object, or create a new one if none exists."""
    return self.table.setdefault(host_id, HostInfo())

  def GetHostInfo(self, host_id):
    """Return an info object for given host, if such exists."""
    return self.table.get(host_id)


class Autoupdate(build_util.BuildObject):
  """Class that contains functionality that handles Chrome OS update pings.

  Members:
    forced_image:    path to an image to use for all updates.
    payload_path:    path to pre-generated payload to serve.
    src_image:       if specified, creates a delta payload from this image.
    proxy_port:      port of local proxy to tell client to connect to you
                     through.
    board:           board for the image. Needed for pre-generating of updates.
    copy_to_static_root:  copies images generated from the cache to ~/static.
    public_key:       path to public key in PEM format.
    critical_update:  whether provisioned payload is critical.
    max_updates:      maximum number of updates we'll try to provision.
    host_log:         record full history of host update events.
  """

  _PAYLOAD_URL_PREFIX = '/static/'

  def __init__(self, xbuddy, forced_image=None, payload_path=None,
               proxy_port=None, src_image='', board=None,
               copy_to_static_root=True, public_key=None,
               critical_update=False, max_updates=-1, host_log=False,
               *args, **kwargs):
    super(Autoupdate, self).__init__(*args, **kwargs)
    self.xbuddy = xbuddy
    self.forced_image = forced_image
    self.payload_path = payload_path
    self.src_image = src_image
    self.proxy_port = proxy_port
    self.board = board or self.GetDefaultBoardID()
    self.copy_to_static_root = copy_to_static_root
    self.public_key = public_key
    self.critical_update = critical_update
    self.max_updates = max_updates
    self.host_log = host_log

    self.pregenerated_path = None

    # Initialize empty host info cache. Used to keep track of various bits of
    # information about a given host.  A host is identified by its IP address.
    # The info stored for each host includes a complete log of events for this
    # host, as well as a dictionary of current attributes derived from events.
    self.host_infos = HostInfoTable()

    self._update_count_lock = threading.Lock()

  @staticmethod
  def _GetVersionFromDir(image_dir):
    """Returns the version of the image based on the name of the directory."""
    latest_version = os.path.basename(image_dir)
    parts = latest_version.split('-')
    # If we can't get a version number from the directory, default to a high
    # number to allow the update to happen
    # TODO(phobbs) refactor this.
    return parts[1] if len(parts) == 3 else '999999.0.0'

  @staticmethod
  def _CanUpdate(client_version, latest_version):
    """True if the latest_version is greater than the client_version."""
    _Log('client version %s latest version %s', client_version, latest_version)

    client_tokens = client_version.replace('_', '').split('.')
    latest_tokens = latest_version.replace('_', '').split('.')

    def _SafeInt(part):
      try:
        return int(part)
      except ValueError:
        return part

    if len(latest_tokens) == len(client_tokens) == 3:
      return map(_SafeInt, latest_tokens) > map(_SafeInt, client_tokens)
    else:
      # If the directory name isn't a version number, let it pass.
      return True

  def GenerateUpdateFile(self, src_image, image_path, output_dir):
    """Generates an update gz given a full path to an image.

    Args:
      src_image: Path to a source image.
      image_path: Full path to image.
      output_dir: Path to the generated update file.

    Raises:
      subprocess.CalledProcessError if the update generator fails to generate an
      update payload.
    """
    update_path = os.path.join(output_dir, constants.UPDATE_FILE)
    _Log('Generating update image %s', update_path)

    update_command = [
        'cros_generate_update_payload',
        '--image', image_path,
        '--output', update_path,
    ]

    if src_image:
      update_command.extend(['--src_image', src_image])

    _Log('Running %s', ' '.join(update_command))
    subprocess.check_call(update_command)

  @staticmethod
  def GenerateStatefulFile(image_path, output_dir):
    """Generates a stateful update payload given a full path to an image.

    Args:
      image_path: Full path to image.
      output_dir: Directory for emitting the stateful update payload.

    Raises:
      subprocess.CalledProcessError if the update generator fails to generate a
      stateful payload.
    """
    update_command = [
        'cros_generate_stateful_update_payload',
        '--image', image_path,
        '--output_dir', output_dir,
    ]
    _Log('Running %s', ' '.join(update_command))
    subprocess.check_call(update_command)

  def FindCachedUpdateImageSubDir(self, src_image, dest_image):
    """Find directory to store a cached update.

    Given one, or two images for an update, this finds which cache directory
    should hold the update files, even if they don't exist yet.

    Returns:
      A directory path for storing a cached update, of the following form:
        Non-delta updates:
          CACHE_DIR/<dest_hash>
        Delta updates:
          CACHE_DIR/<src_hash>_<dest_hash>
    """
    update_dir = ''
    if src_image:
      update_dir += common_util.GetFileMd5(src_image) + '_'

    update_dir += common_util.GetFileMd5(dest_image)

    return os.path.join(constants.CACHE_DIR, update_dir)

  def GenerateUpdateImage(self, image_path, output_dir):
    """Force generates an update payload based on the given image_path.

    Args:
      image_path: full path to the image.
      output_dir: the directory to write the update payloads to

    Raises:
      AutoupdateError if it failed to generate either update or stateful
        payload.
    """
    _Log('Generating update for image %s', image_path)

    # Delete any previous state in this directory.
    os.system('rm -rf "%s"' % output_dir)
    os.makedirs(output_dir)

    try:
      self.GenerateUpdateFile(self.src_image, image_path, output_dir)
      self.GenerateStatefulFile(image_path, output_dir)
    except subprocess.CalledProcessError:
      os.system('rm -rf "%s"' % output_dir)
      raise AutoupdateError('Failed to generate update in %s' % output_dir)

  def GenerateUpdateImageWithCache(self, image_path):
    """Force generates an update payload based on the given image_path.

    Args:
      image_path: full path to the image.

    Returns:
      update directory relative to static_image_dir.

    Raises:
      AutoupdateError if it we need to generate a payload and fail to do so.
    """
    _Log('Generating update for src %s image %s', self.src_image, image_path)

    # If it was pregenerated, don't regenerate.
    if self.pregenerated_path:
      return self.pregenerated_path

    # Which sub_dir should hold our cached update image.
    cache_sub_dir = self.FindCachedUpdateImageSubDir(self.src_image, image_path)
    _Log('Caching in sub_dir "%s"', cache_sub_dir)

    # The cached payloads exist in a cache dir.
    cache_dir = os.path.join(self.static_dir, cache_sub_dir)

    cache_update_payload = os.path.join(cache_dir,
                                        constants.UPDATE_FILE)
    cache_stateful_payload = os.path.join(cache_dir,
                                          constants.STATEFUL_FILE)
    # Check to see if this cache directory is valid.
    if not (os.path.exists(cache_update_payload) and
            os.path.exists(cache_stateful_payload)):
      self.GenerateUpdateImage(image_path, cache_dir)

    # Don't regenerate the image for this devserver instance.
    self.pregenerated_path = cache_sub_dir

    return cache_sub_dir

  def _SymlinkUpdateFiles(self, target_dir, link_dir):
    """Symlinks the update-related files from target_dir to link_dir.

    Every time an update is called, clear existing files/symlinks in the
    link_dir, and replace them with symlinks to the target_dir.

    Args:
      target_dir: Location of the target files.
      link_dir: Directory where the links should exist after.
    """
    _Log('Linking %s to %s', target_dir, link_dir)
    if link_dir == target_dir:
      _Log('Cannot symlink into the same directory.')
      return
    for _, _, files in os.walk(target_dir):
      for target in files:
        link = os.path.join(link_dir, target)
        target = os.path.join(target_dir, target)
        common_util.SymlinkFile(target, link)

  def GetUpdateForLabel(self, client_version, label,
                        image_name=constants.TEST_IMAGE_FILE):
    """Given a label, get an update from the directory.

    Args:
      client_version: Current version of the client or FORCED_UPDATE
      label: the relative directory inside the static dir
      image_name: If the image type was specified by the update rpc, we try to
        find an image with this file name first. This is by default
        "chromiumos_test_image.bin" but can also take any of the values in
        devserver_constants.ALL_IMAGES

    Returns:
      A relative path to the directory with the update payload.
      This is the label if an update did not need to be generated, but can
      be label/cache/hashed_dir_for_update.

    Raises:
      AutoupdateError: If client version is higher than available update found
        at the directory given by the label.
    """
    _Log('Update label/file: %s/%s', label, image_name)
    static_image_dir = _NonePathJoin(self.static_dir, label)
    static_update_path = _NonePathJoin(static_image_dir, constants.UPDATE_FILE)
    static_image_path = _NonePathJoin(static_image_dir, image_name)

    # Update the client only if client version is older than available update.
    latest_version = self._GetVersionFromDir(static_image_dir)
    if not (client_version == FORCED_UPDATE or
            self._CanUpdate(client_version, latest_version)):
      raise AutoupdateError(
          'Update check received but no update available for client')

    if label and os.path.exists(static_update_path):
      # An update payload was found for the given label, return it.
      return label
    elif os.path.exists(static_image_path) and common_util.IsInsideChroot():
      # Image was found for the given label. Generate update if we can.
      rel_path = self.GenerateUpdateImageWithCache(static_image_path)
      # Add links from the static directory to the update.
      cache_path = _NonePathJoin(self.static_dir, rel_path)
      self._SymlinkUpdateFiles(cache_path, static_image_dir)
      return label

    # The label didn't resolve.
    return None

  def PreGenerateUpdate(self):
    """Pre-generates an update and prints out the relative path it.

    Returns relative path of the update.

    Raises:
      AutoupdateError if it failed to generate the payload.
    """
    _Log('Pre-generating the update payload')
    # Does not work with labels so just use static dir. (empty label)
    pregenerated_update = self.GetPathToPayload('', FORCED_UPDATE, self.board)
    print('PREGENERATED_UPDATE=%s' % _NonePathJoin(pregenerated_update,
                                                   constants.UPDATE_FILE))
    return pregenerated_update

  def _ProcessUpdateComponents(self, request):
    """Processes the components of an update request.

    Args:
      request: A nebraska.Request object representing the update request.

    Returns:
      A named tuple containing attributes of the update requests as the
      following fields: 'forced_update_label', 'client_version', 'board',
      'event_result' and 'event_type'.
    """
    # Initialize an empty dictionary for event attributes to log.
    log_message = {}

    # Determine request IP, strip any IPv6 data for simplicity.
    client_ip = cherrypy.request.remote.ip.split(':')[-1]
    # Obtain (or init) info object for this client.
    curr_host_info = self.host_infos.GetInitHostInfo(client_ip)

    client_version = FORCED_UPDATE
    board = None
    event_result = None
    event_type = None
    if request.request_type != nebraska.Request.RequestType.EVENT:
      client_version = request.version
      channel = request.track
      board = request.board or self.GetDefaultBoardID()
      # Add attributes to log message
      log_message['version'] = client_version
      log_message['track'] = channel
      log_message['board'] = board
      curr_host_info.attrs['last_known_version'] = client_version

    else:
      event_result = request.app_requests[0].event_result
      event_type = request.app_requests[0].event_type
      client_previous_version = request.app_requests[0].previous_version
      # Store attributes to legacy host info structure
      curr_host_info.attrs['last_event_status'] = event_result
      curr_host_info.attrs['last_event_type'] = event_type
      # Add attributes to log message
      log_message['event_result'] = event_result
      log_message['event_type'] = event_type
      if client_previous_version is not None:
        log_message['previous_version'] = client_previous_version

    # Log host event, if so instructed.
    if self.host_log:
      curr_host_info.AddLogEntry(log_message)

    UpdateRequestAttrs = collections.namedtuple(
        'UpdateRequestAttrs',
        ('forced_update_label', 'client_version', 'board', 'event_result',
         'event_type'))

    return UpdateRequestAttrs(
        curr_host_info.attrs.pop('forced_update_label', None),
        client_version, board, event_result, event_type)

  def GetDevserverUrl(self):
    """Returns the devserver url base."""
    x_forwarded_host = cherrypy.request.headers.get('X-Forwarded-Host')
    if x_forwarded_host:
      hostname = 'http://' + x_forwarded_host
    else:
      hostname = cherrypy.request.base

    return hostname

  def GetStaticUrl(self):
    """Returns the static url base that should prefix all payload responses."""
    hostname = self.GetDevserverUrl()

    static_urlbase = '%s/static' % hostname
    # If we have a proxy port, adjust the URL we instruct the client to
    # use to go through the proxy.
    if self.proxy_port:
      static_urlbase = _ChangeUrlPort(static_urlbase, self.proxy_port)

    _Log('Using static url base %s', static_urlbase)
    _Log('Handling update ping as %s', hostname)
    return static_urlbase

  def GetPathToPayload(self, label, client_version, board):
    """Find a payload locally.

    See devserver's update rpc for documentation.

    Args:
      label: from update request
      client_version: from update request
      board: from update request

    Returns:
      The relative path to an update from the static_dir

    Raises:
      AutoupdateError: If the update could not be found.
    """
    path_to_payload = None
    #TODO(joychen): deprecate --payload flag
    if self.payload_path:
      # Copy the image from the path to '/forced_payload'
      label = 'forced_payload'
      dest_path = os.path.join(self.static_dir, label, constants.UPDATE_FILE)
      dest_stateful = os.path.join(self.static_dir, label,
                                   constants.STATEFUL_FILE)
      dest_meta = os.path.join(self.static_dir, label,
                               constants.UPDATE_METADATA_FILE)

      src_path = os.path.abspath(self.payload_path)
      src_stateful = os.path.join(os.path.dirname(src_path),
                                  constants.STATEFUL_FILE)
      common_util.MkDirP(os.path.join(self.static_dir, label))
      common_util.SymlinkFile(src_path, dest_path)
      # The old metadata file should be regenerated whenever a new payload is
      # used.
      try:
        os.unlink(dest_meta)
      except OSError:
        pass
      if os.path.exists(src_stateful):
        # The stateful payload is optional.
        common_util.SymlinkFile(src_stateful, dest_stateful)
      else:
        _Log('WARN: %s not found. Expected for dev and test builds',
             constants.STATEFUL_FILE)
        if os.path.exists(dest_stateful):
          os.remove(dest_stateful)
      path_to_payload = self.GetUpdateForLabel(client_version, label)
    #TODO(joychen): deprecate --image flag
    elif self.forced_image:
      if self.forced_image.startswith('xbuddy:'):
        # This is trying to use an xbuddy path in place of a path to an image.
        xbuddy_label = self.forced_image.split(':')[1]
        self.forced_image = None
        # Make sure the xbuddy path target is in the directory.
        path_to_payload, _image_name = self.xbuddy.Get(xbuddy_label.split('/'))
        # Pretend to have called update with this update path to payload.
        self.GetPathToPayload(xbuddy_label, client_version, board)
      else:
        src_path = os.path.abspath(self.forced_image)
        if os.path.exists(src_path) and common_util.IsInsideChroot():
          # Image was found for the given label. Generate update if we can.
          path_to_payload = self.GenerateUpdateImageWithCache(src_path)
          # Add links from the static directory to the update.
          cache_path = _NonePathJoin(self.static_dir, path_to_payload)
          self._SymlinkUpdateFiles(cache_path, self.static_dir)
    else:
      label = label or ''
      label_list = label.split('/')
      # Suppose that the path follows old protocol of indexing straight
      # into static_dir with board/version label.
      # Attempt to get the update in that directory, generating if necc.
      path_to_payload = self.GetUpdateForLabel(client_version, label)
      if path_to_payload is None:
        # There was no update or image found in the directory.
        # Let XBuddy find an image, and then generate an update to it.
        if label_list[0] == 'xbuddy':
          # If path explicitly calls xbuddy, pop off the tag.
          label_list.pop()
        x_label, image_name = self.xbuddy.Translate(label_list, board=board)
        if image_name not in constants.ALL_IMAGES:
          raise AutoupdateError(
              'Use an image alias: dev, base, test, or recovery.')
        # Path has been resolved, try to get the image.
        path_to_payload = self.GetUpdateForLabel(client_version, x_label,
                                                 image_name)
        if path_to_payload is None:
          # Neither image nor update payload found after translation.
          # Try to get an update to a test image from GS using the label.
          path_to_payload, _image_name = self.xbuddy.Get(
              ['remote', label, 'full_payload'])

    # One of the above options should have gotten us a relative path.
    if path_to_payload is None:
      raise AutoupdateError('Failed to get an update for: %s' % label)

    return path_to_payload

  def HandleUpdatePing(self, data, label=''):
    """Handles an update ping from an update client.

    Args:
      data: XML blob from client.
      label: optional label for the update.

    Returns:
      Update payload message for client.
    """
    # Get the static url base that will form that base of our update url e.g.
    # http://hostname:8080/static/update.gz.
    static_urlbase = self.GetStaticUrl()

    # Process attributes of the update check.
    request = nebraska.Request(data)
    request_attrs = self._ProcessUpdateComponents(request)

    if request.request_type == nebraska.Request.RequestType.EVENT:
      if ((request_attrs.event_type ==
           nebraska.Request.EVENT_TYPE_UPDATE_DOWNLOAD_STARTED) and
          request_attrs.event_result == nebraska.Request.EVENT_RESULT_SUCCESS):
        with self._update_count_lock:
          if self.max_updates == 0:
            _Log('Received too many download_started notifications. This '
                 'probably means a bug in the test environment, such as too '
                 'many clients running concurrently. Alternatively, it could '
                 'be a bug in the update client.')
          elif self.max_updates > 0:
            self.max_updates -= 1

      _Log('A non-update event notification received. Returning an ack.')
      nebraska_obj = nebraska.Nebraska()
      return nebraska_obj.GetResponseToRequest(request)

    # Make sure that we did not already exceed the max number of allowed update
    # responses. Note that the counter is only decremented when the client
    # reports an actual download, to avoid race conditions between concurrent
    # update requests from the same client due to a timeout.
    if self.max_updates == 0:
      _Log('Request received but max number of updates already served.')
      nebraska_obj = nebraska.Nebraska()
      return nebraska_obj.GetResponseToRequest(request, no_update=True)

    if request_attrs.forced_update_label:
      if label:
        _Log('Label: %s set but being overwritten to %s by request', label,
             request_attrs.forced_update_label)
      label = request_attrs.forced_update_label

    _Log('Update Check Received.')

    try:
      path_to_payload = self.GetPathToPayload(
          label, request_attrs.client_version, request_attrs.board)
      base_url = _NonePathJoin(static_urlbase, path_to_payload)
      local_payload_dir = _NonePathJoin(self.static_dir, path_to_payload)
    except AutoupdateError as e:
      # Raised if we fail to generate an update payload.
      _Log('Failed to process an update request, but we will defer to '
           'nebraska to respond with no-update. The error was %s', e)

    _Log('Responding to client to use url %s to get image', base_url)
    nebraska_obj = nebraska.Nebraska(update_payloads_address=base_url,
                                     update_metadata_dir=local_payload_dir)
    return nebraska_obj.GetResponseToRequest(
        request, critical_update=self.critical_update)

  def HandleHostInfoPing(self, ip):
    """Returns host info dictionary for the given IP in JSON format."""
    assert ip, 'No ip provided.'
    if ip in self.host_infos.table:
      return json.dumps(self.host_infos.GetHostInfo(ip).attrs)

  def HandleHostLogPing(self, ip):
    """Returns a complete log of events for host in JSON format."""
    # If all events requested, return a dictionary of logs keyed by IP address.
    if ip == 'all':
      return json.dumps(
          dict([(key, self.host_infos.table[key].log)
                for key in self.host_infos.table]))

    # Otherwise we're looking for a specific IP address, so find its log.
    if ip in self.host_infos.table:
      return json.dumps(self.host_infos.GetHostInfo(ip).log)

    # If no events were logged for this IP, return an empty log.
    return json.dumps([])

  def HandleSetUpdatePing(self, ip, label):
    """Sets forced_update_label for a given host."""
    assert ip, 'No ip provided.'
    assert label, 'No label provided.'
    self.host_infos.GetInitHostInfo(ip).attrs['forced_update_label'] = label
