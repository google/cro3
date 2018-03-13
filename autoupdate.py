# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Devserver module for handling update client requests."""

from __future__ import print_function

import base64
import collections
import fcntl
import json
import os
import subprocess
import sys
import threading
import time
import urllib2
import urlparse

import cherrypy

import build_util
import autoupdate_lib
import common_util
import devserver_constants as constants
import log_util
# pylint: disable=F0401

# Allow importing from aosp/system/update_engine/scripts when running from
# source tree. Used for importing update_payload if it is not in the system
# path.
lib_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'aosp',
                       'system', 'update_engine', 'scripts')
if os.path.exists(lib_dir) and os.path.isdir(lib_dir):
  sys.path.insert(1, lib_dir)
import update_payload


# If used by client in place of an pre-update version string, forces an update
# to the client regardless of the relative versions of the payload and client.
FORCED_UPDATE = 'ForcedUpdate'

# Files needed to serve an update.
UPDATE_FILES = (
    constants.UPDATE_FILE,
    constants.STATEFUL_FILE,
    constants.METADATA_FILE
)

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


class UpdateMetadata(object):
  """Object containing metadata about an update payload."""

  def __init__(self, sha1, sha256, size, is_delta_format, metadata_size,
               metadata_hash):
    self.sha1 = sha1
    self.sha256 = sha256
    self.size = size
    self.is_delta_format = is_delta_format
    self.metadata_size = metadata_size
    self.metadata_hash = metadata_hash


class Autoupdate(build_util.BuildObject):
  """Class that contains functionality that handles Chrome OS update pings.

  Members:
    urlbase:         base URL, other than devserver, for update images.
    forced_image:    path to an image to use for all updates.
    payload_path:    path to pre-generated payload to serve.
    src_image:       if specified, creates a delta payload from this image.
    proxy_port:      port of local proxy to tell client to connect to you
                     through.
    board:           board for the image. Needed for pre-generating of updates.
    copy_to_static_root:  copies images generated from the cache to ~/static.
    private_key:          path to private key in PEM format.
    private_key_for_metadata_hash_signature: path to private key in PEM format.
    public_key:       path to public key in PEM format.
    critical_update:  whether provisioned payload is critical.
    remote_payload:   whether provisioned payload is remotely staged.
    max_updates:      maximum number of updates we'll try to provision.
    host_log:         record full history of host update events.
  """

  _OLD_PAYLOAD_URL_PREFIX = '/static/archive'
  _PAYLOAD_URL_PREFIX = '/static/'
  _FILEINFO_URL_PREFIX = '/api/fileinfo/'

  SHA1_ATTR = 'sha1'
  SHA256_ATTR = 'sha256'
  SIZE_ATTR = 'size'
  ISDELTA_ATTR = 'is_delta'
  METADATA_SIZE_ATTR = 'metadata_size'
  METADATA_HASH_ATTR = 'metadata_hash'

  def __init__(self, xbuddy, urlbase=None, forced_image=None, payload_path=None,
               proxy_port=None, src_image='', board=None,
               copy_to_static_root=True, private_key=None,
               private_key_for_metadata_hash_signature=None, public_key=None,
               critical_update=False, remote_payload=False, max_updates=-1,
               host_log=False, *args, **kwargs):
    super(Autoupdate, self).__init__(*args, **kwargs)
    self.xbuddy = xbuddy
    self.urlbase = urlbase or None
    self.forced_image = forced_image
    self.payload_path = payload_path
    self.src_image = src_image
    self.proxy_port = proxy_port
    self.board = board or self.GetDefaultBoardID()
    self.copy_to_static_root = copy_to_static_root
    self.private_key = private_key
    self.private_key_for_metadata_hash_signature = \
      private_key_for_metadata_hash_signature
    self.public_key = public_key
    self.critical_update = critical_update
    self.remote_payload = remote_payload
    self.max_updates = max_updates
    self.host_log = host_log

    self.pregenerated_path = None

    # Initialize empty host info cache. Used to keep track of various bits of
    # information about a given host.  A host is identified by its IP address.
    # The info stored for each host includes a complete log of events for this
    # host, as well as a dictionary of current attributes derived from events.
    self.host_infos = HostInfoTable()

    self._update_count_lock = threading.Lock()

  @classmethod
  def _ReadMetadataFromStream(cls, stream):
    """Returns metadata obj from input json stream that implements .read()."""
    data = None
    file_attr_dict = {}
    try:
      data = stream.read()
      file_attr_dict = json.loads(data)
    except (IOError, ValueError):
      _Log('Failed to load metadata:%s' % data)
      return None

    sha1 = file_attr_dict.get(cls.SHA1_ATTR)
    sha256 = file_attr_dict.get(cls.SHA256_ATTR)
    size = file_attr_dict.get(cls.SIZE_ATTR)
    is_delta = file_attr_dict.get(cls.ISDELTA_ATTR)
    metadata_size = file_attr_dict.get(cls.METADATA_SIZE_ATTR)
    metadata_hash = file_attr_dict.get(cls.METADATA_HASH_ATTR)
    return UpdateMetadata(sha1, sha256, size, is_delta, metadata_size,
                          metadata_hash)

  @staticmethod
  def _ReadMetadataFromFile(payload_dir):
    """Returns metadata object from the metadata_file in the payload_dir"""
    metadata_file = os.path.join(payload_dir, constants.METADATA_FILE)
    if os.path.exists(metadata_file):
      metadata_stream = open(metadata_file, 'r')
      fcntl.lockf(metadata_stream.fileno(), fcntl.LOCK_SH)
      metadata = Autoupdate._ReadMetadataFromStream(metadata_stream)
      fcntl.lockf(metadata_stream.fileno(), fcntl.LOCK_UN)
      return metadata

  @classmethod
  def _StoreMetadataToFile(cls, payload_dir, metadata_obj):
    """Stores metadata object into the metadata_file of the payload_dir"""
    file_dict = {cls.SHA1_ATTR: metadata_obj.sha1,
                 cls.SHA256_ATTR: metadata_obj.sha256,
                 cls.SIZE_ATTR: metadata_obj.size,
                 cls.ISDELTA_ATTR: metadata_obj.is_delta_format,
                 cls.METADATA_SIZE_ATTR: metadata_obj.metadata_size,
                 cls.METADATA_HASH_ATTR: metadata_obj.metadata_hash}
    metadata_file = os.path.join(payload_dir, constants.METADATA_FILE)
    file_handle = open(metadata_file, 'w')
    fcntl.lockf(file_handle.fileno(), fcntl.LOCK_EX)
    json.dump(file_dict, file_handle)
    fcntl.lockf(file_handle.fileno(), fcntl.LOCK_UN)

  @staticmethod
  def _GetVersionFromDir(image_dir):
    """Returns the version of the image based on the name of the directory."""
    latest_version = os.path.basename(image_dir)
    parts = latest_version.split('-')
    # If we can't get a version number from the directory, default to a high
    # number to allow the update to happen
    # TODO(phobbs) refactor this.
    return parts[1] if len(parts) == 3 else "999999.0.0"

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

  @staticmethod
  def IsDeltaFormatFile(filename):
    try:
      with open(filename) as payload_file:
        payload = update_payload.Payload(payload_file)
        payload.Init()
        return payload.IsDelta()
    except (IOError, update_payload.PayloadError):
      # For unit tests we may not have real files, so it's ok to ignore these
      # errors.
      return False

  def GenerateUpdateFile(self, src_image, image_path, output_dir):
    """Generates an update gz given a full path to an image.

    Args:
      src_image: Path to a source image.
      image_path: Full path to image.
      output_dir: Path to the generated update file.

    Raises:
      subprocess.CalledProcessError if the update generator fails to generate a
      stateful payload.
    """
    update_path = os.path.join(output_dir, constants.UPDATE_FILE)
    _Log('Generating update image %s', update_path)

    update_command = [
        'cros_generate_update_payload',
        '--image', image_path,
        '--out_metadata_hash_file', os.path.join(output_dir,
                                                 constants.METADATA_HASH_FILE),
        '--output', update_path,
    ]

    if src_image:
      update_command.extend(['--src_image', src_image])

    if self.private_key:
      update_command.extend(['--private_key', self.private_key])

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
        Signed updates (self.private_key):
          CACHE_DIR/<src_hash>_<dest_hash>+<private_key_hash>
    """
    update_dir = ''
    if src_image:
      update_dir += common_util.GetFileMd5(src_image) + '_'

    update_dir += common_util.GetFileMd5(dest_image)
    if self.private_key:
      update_dir += '+' + common_util.GetFileMd5(self.private_key)

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

    # Generate the cache file.
    self.GetLocalPayloadAttrs(cache_dir)

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
    for f in UPDATE_FILES:
      link = os.path.join(link_dir, f)
      target = os.path.join(target_dir, f)
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

  def _GetRemotePayloadAttrs(self, url):
    """Returns hashes, size and delta flag of a remote update payload.

    Obtain attributes of a payload file available on a remote devserver. This
    is based on the assumption that the payload URL uses the /static prefix. We
    need to make sure that both clients (requests) and remote devserver
    (provisioning) preserve this invariant.

    Args:
      url: URL of statically staged remote file (http://host:port/static/...)

    Returns:
      A UpdateMetadata object.
    """
    if self._PAYLOAD_URL_PREFIX not in url:
      raise AutoupdateError(
          'Payload URL does not have the expected prefix (%s)' %
          self._PAYLOAD_URL_PREFIX)

    if self._OLD_PAYLOAD_URL_PREFIX in url:
      fileinfo_url = url.replace(self._OLD_PAYLOAD_URL_PREFIX,
                                 self._FILEINFO_URL_PREFIX)
    else:
      fileinfo_url = url.replace(self._PAYLOAD_URL_PREFIX,
                                 self._FILEINFO_URL_PREFIX)

    _Log('Retrieving file info for remote payload via %s', fileinfo_url)
    try:
      conn = urllib2.urlopen(fileinfo_url)
      metadata_obj = Autoupdate._ReadMetadataFromStream(conn)
      # These fields are required for remote calls.
      if not metadata_obj:
        raise AutoupdateError('Failed to obtain remote payload info')

      return metadata_obj
    except IOError as e:
      raise AutoupdateError('Failed to obtain remote payload info: %s', e)

  @staticmethod
  def _GetMetadataHash(payload_dir):
    """Gets the metadata hash, if it exists.

    Args:
      payload_dir: The payload directory.

    Returns:
      The metadata hash, base-64 encoded or None if there is no metadata hash.
    """
    path = os.path.join(payload_dir, constants.METADATA_HASH_FILE)
    if os.path.exists(path):
      return base64.b64encode(open(path, 'rb').read())
    else:
      return None

  @staticmethod
  def _GetMetadataSize(payload_filename):
    """Gets the size of the metadata in a payload file.

    Args:
      payload_filename: Path to the payload file.

    Returns:
      The size of the payload metadata, as reported in the payload header.
    """
    try:
      with open(payload_filename) as payload_file:
        payload = update_payload.Payload(payload_file)
        payload.Init()
        return payload.metadata_size
    except (IOError, update_payload.PayloadError):
      # For unit tests we may not have real files, so it's ok to ignore these
      # errors.
      return 0

  def GetLocalPayloadAttrs(self, payload_dir):
    """Returns hashes, size and delta flag of a local update payload.

    Args:
      payload_dir: Path to the directory the payload is in.

    Returns:
      A UpdateMetadata object.
    """
    filename = os.path.join(payload_dir, constants.UPDATE_FILE)
    if not os.path.exists(filename):
      raise AutoupdateError('update.gz not present in payload dir %s' %
                            payload_dir)

    metadata_obj = Autoupdate._ReadMetadataFromFile(payload_dir)
    if not metadata_obj or not (metadata_obj.sha1 and
                                metadata_obj.sha256 and
                                metadata_obj.size):
      sha1 = common_util.GetFileSha1(filename)
      sha256 = common_util.GetFileSha256(filename)
      size = common_util.GetFileSize(filename)
      is_delta_format = self.IsDeltaFormatFile(filename)
      metadata_size = self._GetMetadataSize(filename)
      metadata_hash = self._GetMetadataHash(payload_dir)
      metadata_obj = UpdateMetadata(sha1, sha256, size, is_delta_format,
                                    metadata_size, metadata_hash)
      Autoupdate._StoreMetadataToFile(payload_dir, metadata_obj)

    return metadata_obj

  def _ProcessUpdateComponents(self, app, event):
    """Processes the components of an update request.

    Args:
      app: An app component of an update request.
      event: An event component of an update request.

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
    if app:
      client_version = app.getAttribute('version')
      channel = app.getAttribute('track')
      board = (app.hasAttribute('board') and app.getAttribute('board')
               or self.GetDefaultBoardID())
      # Add attributes to log message
      log_message['version'] = client_version
      log_message['track'] = channel
      log_message['board'] = board
      curr_host_info.attrs['last_known_version'] = client_version

    event_result = None
    event_type = None
    if event:
      event_result = int(event[0].getAttribute('eventresult'))
      event_type = int(event[0].getAttribute('eventtype'))
      client_previous_version = (event[0].getAttribute('previousversion')
                                 if event[0].hasAttribute('previousversion')
                                 else None)
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

  @classmethod
  def _CheckOmahaRequest(cls, app):
    """Checks |app| component of Omaha Request for correctly formed data.

    Raises:
      common_util.DevServerHTTPError: if any check fails. All 400 error codes to
          indicate a bad HTTP request.
    """
    if not app:
      raise common_util.DevServerHTTPError(
          400, 'Missing app component in Omaha Request')

    hardware_class = app.getAttribute('hardware_class')
    if not hardware_class:
      raise common_util.DevServerHTTPError(
          400, 'hardware_class is required in Omaha Request')

    track = app.getAttribute('track')
    if not (track and track.endswith('-channel')):
      raise common_util.DevServerHTTPError(
          400, 'Omaha requests need a valid update channel')

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

    if self.urlbase:
      static_urlbase = self.urlbase
    else:
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
      dest_meta = os.path.join(self.static_dir, label, constants.METADATA_FILE)

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
              "Use an image alias: dev, base, test, or recovery.")
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
    else:
      return path_to_payload

  @staticmethod
  def _SignMetadataHash(private_key_path, metadata_hash):
    """Signs metadata hash.

    Signs a metadata hash with a private key. This includes padding the
    hash with PKCS#1 v1.5 padding as well as an ASN.1 header.

    Args:
      private_key_path: The path to a private key to use for signing.
      metadata_hash: A raw SHA-256 hash (32 bytes).

    Returns:
      The raw signature.
    """
    args = ['openssl', 'rsautl', '-pkcs', '-sign', '-inkey', private_key_path]
    padded_metadata_hash = ('\x30\x31\x30\x0d\x06\x09\x60\x86'
                            '\x48\x01\x65\x03\x04\x02\x01\x05'
                            '\x00\x04\x20') + metadata_hash
    child = subprocess.Popen(args,
                             stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE)
    signature, _ = child.communicate(input=padded_metadata_hash)
    return signature

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

    # Parse the XML we got into the components we care about.
    protocol, app, event, update_check = autoupdate_lib.ParseUpdateRequest(data)
    appid = app.getAttribute('appid')

    # Process attributes of the update check.
    request_attrs = self._ProcessUpdateComponents(app, event)

    if not update_check:
      if ((request_attrs.event_type ==
           autoupdate_lib.EVENT_TYPE_UPDATE_DOWNLOAD_STARTED) and
          request_attrs.event_result == autoupdate_lib.EVENT_RESULT_SUCCESS):
        with self._update_count_lock:
          if self.max_updates == 0:
            _Log('Received too many download_started notifications. This '
                 'probably means a bug in the test environment, such as too '
                 'many clients running concurrently. Alternatively, it could '
                 'be a bug in the update client.')
          elif self.max_updates > 0:
            self.max_updates -= 1

      _Log('A non-update event notification received. Returning an ack.')
      return autoupdate_lib.GetEventResponse(protocol, appid)

    if request_attrs.forced_update_label:
      if label:
        _Log('Label: %s set but being overwritten to %s by request', label,
             request_attrs.forced_update_label)
      label = request_attrs.forced_update_label

    # Make sure that we did not already exceed the max number of allowed update
    # responses. Note that the counter is only decremented when the client
    # reports an actual download, to avoid race conditions between concurrent
    # update requests from the same client due to a timeout.
    if self.max_updates == 0:
      _Log('Request received but max number of updates already served.')
      return autoupdate_lib.GetNoUpdateResponse(protocol, appid)

    _Log('Update Check Received. Client is using protocol version: %s',
         protocol)

    # Finally its time to generate the omaha response to give to client that
    # lets them know where to find the payload and its associated metadata.
    metadata_obj = None

    try:
      # Are we provisioning a remote or local payload?
      if self.remote_payload:

        self._CheckOmahaRequest(app)

        # If no explicit label was provided, use the value of --payload.
        if not label:
          label = self.payload_path

        # TODO(sosa): Remove backwards-compatible hack.
        if not '.bin' in label:
          url = _NonePathJoin(static_urlbase, label, 'update.gz')
        else:
          url = _NonePathJoin(static_urlbase, label)

        # Get remote payload attributes.
        metadata_obj = self._GetRemotePayloadAttrs(url)
      else:
        path_to_payload = self.GetPathToPayload(
            label, request_attrs.client_version, request_attrs.board)
        url = _NonePathJoin(static_urlbase, path_to_payload,
                            constants.UPDATE_FILE)
        local_payload_dir = _NonePathJoin(self.static_dir, path_to_payload)
        metadata_obj = self.GetLocalPayloadAttrs(local_payload_dir)
    except AutoupdateError as e:
      # Raised if we fail to generate an update payload.
      _Log('Failed to process an update: %r', e)
      return autoupdate_lib.GetNoUpdateResponse(protocol, appid)

    # Sign the metadata hash, if requested.
    signed_metadata_hash = None
    if self.private_key_for_metadata_hash_signature:
      signed_metadata_hash = base64.b64encode(Autoupdate._SignMetadataHash(
          self.private_key_for_metadata_hash_signature,
          base64.b64decode(metadata_obj.metadata_hash)))

    # Include public key, if requested.
    public_key_data = None
    if self.public_key:
      public_key_data = base64.b64encode(open(self.public_key, 'r').read())

    update_response = autoupdate_lib.GetUpdateResponse(
        metadata_obj.sha1, metadata_obj.sha256, metadata_obj.size, url,
        metadata_obj.is_delta_format, metadata_obj.metadata_size,
        signed_metadata_hash, public_key_data, protocol, appid,
        self.critical_update)

    _Log('Responding to client to use url %s to get image', url)
    return update_response

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
