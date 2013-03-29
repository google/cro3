# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import json
import os
import subprocess
import time
import urllib2
import urlparse

import cherrypy

from build_util import BuildObject
import autoupdate_lib
import common_util
import log_util


# Module-local log function.
def _Log(message, *args):
  return log_util.LogWithTag('UPDATE', message, *args)


UPDATE_FILE = 'update.gz'
METADATA_FILE = 'update.meta'
STATEFUL_FILE = 'stateful.tgz'
CACHE_DIR = 'cache'


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

  print host_port
  netloc = "%s:%s" % tuple(host_port)

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

  def __init__(self, sha1, sha256, size, is_delta_format):
    self.sha1 = sha1
    self.sha256 = sha256
    self.size = size
    self.is_delta_format = is_delta_format


class Autoupdate(BuildObject):
  """Class that contains functionality that handles Chrome OS update pings.

  Members:
    serve_only:      serve only pre-built updates. static_dir must contain
                     update.gz and stateful.tgz.
    use_test_image:  use chromiumos_test_image.bin rather than the standard.
    urlbase:         base URL, other than devserver, for update images.
    forced_image:    path to an image to use for all updates.
    payload_path:    path to pre-generated payload to serve.
    src_image:       if specified, creates a delta payload from this image.
    proxy_port:      port of local proxy to tell client to connect to you
                     through.
    patch_kernel:    Patch the kernel when generating updates
    board:           board for the image. Needed for pre-generating of updates.
    copy_to_static_root:  copies images generated from the cache to ~/static.
    private_key:          path to private key in PEM format.
    critical_update:  whether provisioned payload is critical.
    remote_payload:   whether provisioned payload is remotely staged.
    max_updates:      maximum number of updates we'll try to provision.
    host_log:         record full history of host update events.
  """

  _PAYLOAD_URL_PREFIX = '/static/'
  _FILEINFO_URL_PREFIX = '/api/fileinfo/'

  SHA1_ATTR = 'sha1'
  SHA256_ATTR = 'sha256'
  SIZE_ATTR = 'size'
  ISDELTA_ATTR = 'is_delta'

  def __init__(self, serve_only=None, test_image=False, urlbase=None,
               forced_image=None, payload_path=None,
               proxy_port=None, src_image='', patch_kernel=True, board=None,
               copy_to_static_root=True, private_key=None,
               critical_update=False, remote_payload=False, max_updates= -1,
               host_log=False, *args, **kwargs):
    super(Autoupdate, self).__init__(*args, **kwargs)
    self.serve_only = serve_only
    self.use_test_image = test_image
    if urlbase:
      self.urlbase = urlbase
    else:
      self.urlbase = None

    self.forced_image = forced_image
    self.payload_path = payload_path
    self.src_image = src_image
    self.proxy_port = proxy_port
    self.patch_kernel = patch_kernel
    self.board = board
    self.copy_to_static_root = copy_to_static_root
    self.private_key = private_key
    self.critical_update = critical_update
    self.remote_payload = remote_payload
    self.max_updates = max_updates
    self.host_log = host_log

    # Path to pre-generated file.
    self.pregenerated_path = None

    # Initialize empty host info cache. Used to keep track of various bits of
    # information about a given host.  A host is identified by its IP address.
    # The info stored for each host includes a complete log of events for this
    # host, as well as a dictionary of current attributes derived from events.
    self.host_infos = HostInfoTable()

  @classmethod
  def _ReadMetadataFromStream(cls, stream):
    """Returns metadata obj from input json stream that implements .read()."""
    file_attr_dict = {}
    try:
      file_attr_dict = json.loads(stream.read())
    except IOError:
      return None

    sha1 = file_attr_dict.get(cls.SHA1_ATTR)
    sha256 = file_attr_dict.get(cls.SHA256_ATTR)
    size = file_attr_dict.get(cls.SIZE_ATTR)
    is_delta = file_attr_dict.get(cls.ISDELTA_ATTR)
    return UpdateMetadata(sha1, sha256, size, is_delta)

  @staticmethod
  def _ReadMetadataFromFile(payload_dir):
    """Returns metadata object from the metadata_file in the payload_dir"""
    metadata_file = os.path.join(payload_dir, METADATA_FILE)
    if os.path.exists(metadata_file):
      with open(metadata_file, 'r') as metadata_stream:
        return Autoupdate._ReadMetadataFromStream(metadata_stream)

  @classmethod
  def _StoreMetadataToFile(cls, payload_dir, metadata_obj):
    """Stores metadata object into the metadata_file of the payload_dir"""
    file_dict = {cls.SHA1_ATTR: metadata_obj.sha1,
                 cls.SHA256_ATTR: metadata_obj.sha256,
                 cls.SIZE_ATTR: metadata_obj.size,
                 cls.ISDELTA_ATTR: metadata_obj.is_delta_format}
    metadata_file = os.path.join(payload_dir, METADATA_FILE)
    with open(metadata_file, 'w') as file_handle:
      json.dump(file_dict, file_handle)

  def _GetDefaultBoardID(self):
    """Returns the default board id stored in .default_board."""
    board_file = '%s/.default_board' % (self.scripts_dir)
    try:
      return open(board_file).read()
    except IOError:
      return 'x86-generic'

  def _GetLatestImageDir(self, board):
    """Returns the latest image dir based on shell script."""
    cmd = '%s/get_latest_image.sh --board %s' % (self.scripts_dir, board)
    return os.popen(cmd).read().strip()

  @staticmethod
  def _GetVersionFromDir(image_dir):
    """Returns the version of the image based on the name of the directory."""
    latest_version = os.path.basename(image_dir)
    parts = latest_version.split('-')
    if len(parts) == 2:
      # Old-style, e.g. "0.15.938.2011_08_23_0941-a1".
      # TODO(derat): Remove the code for old-style versions after 20120101.
      return parts[0]
    else:
      # New-style, e.g. "R16-1102.0.2011_09_30_0806-a1".
      return parts[1]

  @staticmethod
  def _CanUpdate(client_version, latest_version):
    """Returns true if the latest_version is greater than the client_version.
    """
    _Log('client version %s latest version %s', client_version, latest_version)

    client_tokens = client_version.replace('_', '').split('.')
    # If the client has an old four-token version like "0.16.892.0", drop the
    # first two tokens -- we use versions like "892.0.0" now.
    # TODO(derat): Remove the code for old-style versions after 20120101.
    if len(client_tokens) == 4:
      client_tokens = client_tokens[2:]

    latest_tokens = latest_version.replace('_', '').split('.')
    if len(latest_tokens) == 4:
      latest_tokens = latest_tokens[2:]

    for i in range(min(len(client_tokens), len(latest_tokens))):
      if int(latest_tokens[i]) == int(client_tokens[i]):
        continue
      return int(latest_tokens[i]) > int(client_tokens[i])

    # Favor four-token new-style versions on the server over old-style versions
    # on the client if everything else matches.
    return len(latest_tokens) > len(client_tokens)

  def _GetImageName(self):
    """Returns the name of the image that should be used."""
    if self.use_test_image:
      image_name = 'chromiumos_test_image.bin'
    else:
      image_name = 'chromiumos_image.bin'

    return image_name

  @staticmethod
  def _IsDeltaFormatFile(filename):
    try:
      file_handle = open(filename, 'r')
      delta_magic = 'CrAU'
      magic = file_handle.read(len(delta_magic))
      return magic == delta_magic
    except IOError:
      # For unit tests, we may not have real files, so it's ok to
      # ignore these IOErrors. In any case, this value is not being
      # used in update_engine at all as of now.
      return False

  def GenerateUpdateFile(self, src_image, image_path, output_dir):
    """Generates an update gz given a full path to an image.

    Args:
      image_path: Full path to image.
    Raises:
      subprocess.CalledProcessError if the update generator fails to generate a
      stateful payload.
    """
    update_path = os.path.join(output_dir, UPDATE_FILE)
    _Log('Generating update image %s', update_path)

    update_command = [
        'cros_generate_update_payload',
        '--image', image_path,
        '--output', update_path,
    ]

    if src_image:
      update_command.extend(['--src_image', src_image])

    if self.patch_kernel:
      update_command.append('--patch_kernel')

    if self.private_key:
      update_command.extend(['--private_key', self.private_key])

    _Log('Running %s', ' '.join(update_command))
    subprocess.check_call(update_command)

  @staticmethod
  def GenerateStatefulFile(image_path, output_dir):
    """Generates a stateful update payload given a full path to an image.

    Args:
      image_path: Full path to image.
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

    if self.patch_kernel:
      update_dir += '+patched_kernel'

    return os.path.join(CACHE_DIR, update_dir)

  def GenerateUpdateImage(self, image_path, output_dir):
    """Force generates an update payload based on the given image_path.

    Args:
      src_image: image we are updating from (Null/empty for non-delta)
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

  def GenerateUpdateImageWithCache(self, image_path, static_image_dir):
    """Force generates an update payload based on the given image_path.

    Args:
      image_path: full path to the image.
      static_image_dir: the directory to move images to after generating.
    Returns:
      update directory relative to static_image_dir. None if it should
      serve from the static_image_dir.
    Raises:
      AutoupdateError if it we need to generate a payload and fail to do so.
    """
    _Log('Generating update for src %s image %s', self.src_image, image_path)

    # If it was pregenerated_path, don't regenerate
    if self.pregenerated_path:
      return self.pregenerated_path

    # Which sub_dir of static_image_dir should hold our cached update image
    cache_sub_dir = self.FindCachedUpdateImageSubDir(self.src_image, image_path)
    _Log('Caching in sub_dir "%s"', cache_sub_dir)

    # The cached payloads exist in a cache dir
    cache_update_payload = os.path.join(static_image_dir,
                                        cache_sub_dir, UPDATE_FILE)
    cache_stateful_payload = os.path.join(static_image_dir,
                                          cache_sub_dir, STATEFUL_FILE)

    full_cache_dir = os.path.join(static_image_dir, cache_sub_dir)
    # Check to see if this cache directory is valid.
    if not os.path.exists(cache_update_payload) or not os.path.exists(
        cache_stateful_payload):
      self.GenerateUpdateImage(image_path, full_cache_dir)

    self.pregenerated_path = cache_sub_dir

    # Generate the cache file.
    self.GetLocalPayloadAttrs(full_cache_dir)
    cache_metadata_file = os.path.join(full_cache_dir, METADATA_FILE)

    # Generation complete, copy if requested.
    if self.copy_to_static_root:
      # The final results exist directly in static
      update_payload = os.path.join(static_image_dir,
                                    UPDATE_FILE)
      stateful_payload = os.path.join(static_image_dir,
                                      STATEFUL_FILE)
      metadata_file = os.path.join(static_image_dir, METADATA_FILE)
      common_util.CopyFile(cache_update_payload, update_payload)
      common_util.CopyFile(cache_stateful_payload, stateful_payload)
      common_util.CopyFile(cache_metadata_file, metadata_file)
      return None
    else:
      return self.pregenerated_path

  def GenerateLatestUpdateImage(self, board, client_version,
                                static_image_dir):
    """Generates an update using the latest image that has been built.

    This will only generate an update if the newest update is newer than that
    on the client or client_version is 'ForcedUpdate'.

    Args:
      board: Name of the board.
      client_version: Current version of the client or 'ForcedUpdate'
      static_image_dir: the directory to move images to after generating.
    Returns:
      Name of the update directory relative to the static dir. None if it should
        serve from the static_image_dir.
    Raises:
      AutoupdateError if it failed to generate the payload or can't update
        the given client_version.
    """
    latest_image_dir = self._GetLatestImageDir(board)
    latest_version = self._GetVersionFromDir(latest_image_dir)
    latest_image_path = os.path.join(latest_image_dir, self._GetImageName())

     # Check to see whether or not we should update.
    if client_version != 'ForcedUpdate' and not self._CanUpdate(
        client_version, latest_version):
      raise AutoupdateError('Update check received but no update available '
                            'for client')

    return self.GenerateUpdateImageWithCache(latest_image_path,
                                             static_image_dir=static_image_dir)

  def GenerateUpdatePayload(self, board, client_version, static_image_dir):
    """Generates an update for an image and returns the relative payload dir.

    Returns:
      payload dir relative to static_image_dir. None if it should
      serve from the static_image_dir.
    Raises:
      AutoupdateError if it failed to generate the payload.
    """
    dest_path = os.path.join(static_image_dir, UPDATE_FILE)
    dest_stateful = os.path.join(static_image_dir, STATEFUL_FILE)

    if self.payload_path:
      # If the forced payload is not already in our static_image_dir,
      # copy it there.
      src_path = os.path.abspath(self.payload_path)
      src_stateful = os.path.join(os.path.dirname(src_path), STATEFUL_FILE)
      # Only copy the files if the source directory is different from dest.
      if os.path.dirname(src_path) != os.path.abspath(static_image_dir):
        common_util.CopyFile(src_path, dest_path)

        # The stateful payload is optional.
        if os.path.exists(src_stateful):
          common_util.CopyFile(src_stateful, dest_stateful)
        else:
          _Log('WARN: %s not found. Expected for dev and test builds',
               STATEFUL_FILE)
          if os.path.exists(dest_stateful):
            os.remove(dest_stateful)

      # Serve from the main directory so rel_path is None.
      return None
    elif self.forced_image:
      return self.GenerateUpdateImageWithCache(
          self.forced_image,
          static_image_dir=static_image_dir)
    else:
      if not board:
        raise AutoupdateError(
          'Failed to generate update. '
          'You must set --board when pre-generating latest update.')

      return self.GenerateLatestUpdateImage(board, client_version,
                                            static_image_dir)

  def PreGenerateUpdate(self):
    """Pre-generates an update and prints out the relative path it.

    Returns relative path of the update.

    Raises:
      AutoupdateError if it failed to generate the payload.
    """
    _Log('Pre-generating the update payload')
    # Does not work with labels so just use static dir.
    pregenerated_update = self.GenerateUpdatePayload(self.board, '0.0.0.0',
                                                     self.static_dir)
    print 'PREGENERATED_UPDATE=%s' % _NonePathJoin(pregenerated_update,
                                                   UPDATE_FILE)
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
      A tuple containing the SHA1, SHA256, file size and whether or not it's a
      delta payload (Boolean).
    """
    if self._PAYLOAD_URL_PREFIX not in url:
      raise AutoupdateError(
          'Payload URL does not have the expected prefix (%s)' %
          self._PAYLOAD_URL_PREFIX)

    fileinfo_url = url.replace(self._PAYLOAD_URL_PREFIX,
                               self._FILEINFO_URL_PREFIX)
    _Log('Retrieving file info for remote payload via %s', fileinfo_url)
    try:
      conn = urllib2.urlopen(fileinfo_url)
      metadata_obj = Autoupdate._ReadMetadataFromStream(conn)
      # These fields are required for remote calls.
      if not metadata_obj:
        raise AutoupdateError('Failed to obtain remote payload info')

      if not metadata_obj.is_delta_format:
        metadata_obj.is_delta_format = ('_mton' in url) or ('_nton' in url)

      return metadata_obj
    except IOError as e:
      raise AutoupdateError('Failed to obtain remote payload info: %s', e)

  def GetLocalPayloadAttrs(self, payload_dir):
    """Returns hashes, size and delta flag of a local update payload.

    Args:
      payload_dir: Path to the directory the payload is in.
    Returns:
      A tuple containing the SHA1, SHA256, file size and whether or not it's a
      delta payload (Boolean).
    """
    filename = os.path.join(payload_dir, UPDATE_FILE)
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
      is_delta_format = self._IsDeltaFormatFile(filename)
      metadata_obj = UpdateMetadata(sha1, sha256, size, is_delta_format)
      Autoupdate._StoreMetadataToFile(payload_dir, metadata_obj)

    return metadata_obj

  def _ProcessUpdateComponents(self, app, event):
    """Processes the app and event components of an update request.

    Returns tuple containing forced_update_label, client_version, and board.
    """
    # Initialize an empty dictionary for event attributes to log.
    log_message = {}

    # Determine request IP, strip any IPv6 data for simplicity.
    client_ip = cherrypy.request.remote.ip.split(':')[-1]
    # Obtain (or init) info object for this client.
    curr_host_info = self.host_infos.GetInitHostInfo(client_ip)

    client_version = 'ForcedUpdate'
    board = None
    if app:
      client_version = app.getAttribute('version')
      channel = app.getAttribute('track')
      board = (app.hasAttribute('board') and app.getAttribute('board')
                  or self._GetDefaultBoardID())
      # Add attributes to log message
      log_message['version'] = client_version
      log_message['track'] = channel
      log_message['board'] = board
      curr_host_info.attrs['last_known_version'] = client_version

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

    return (curr_host_info.attrs.pop('forced_update_label', None),
            client_version, board)

  def _GetStaticUrl(self):
    """Returns the static url base that should prefix all payload responses."""
    x_forwarded_host = cherrypy.request.headers.get('X-Forwarded-Host')
    if x_forwarded_host:
      hostname = 'http://' + x_forwarded_host
    else:
      hostname = cherrypy.request.base

    if self.urlbase:
      static_urlbase = self.urlbase
    elif self.serve_only:
      static_urlbase = '%s/static/archive' % hostname
    else:
      static_urlbase = '%s/static' % hostname

    # If we have a proxy port, adjust the URL we instruct the client to
    # use to go through the proxy.
    if self.proxy_port:
      static_urlbase = _ChangeUrlPort(static_urlbase, self.proxy_port)

    _Log('Using static url base %s', static_urlbase)
    _Log('Handling update ping as %s', hostname)
    return static_urlbase

  def HandleUpdatePing(self, data, label=None):
    """Handles an update ping from an update client.

    Args:
      data: XML blob from client.
      label: optional label for the update.
    Returns:
      Update payload message for client.
    """
    # Get the static url base that will form that base of our update url e.g.
    # http://hostname:8080/static/update.gz.
    static_urlbase = self._GetStaticUrl()

    # Parse the XML we got into the components we care about.
    protocol, app, event, update_check = autoupdate_lib.ParseUpdateRequest(data)

    # #########################################################################
    # Process attributes of the update check.
    forced_update_label, client_version, board = self._ProcessUpdateComponents(
        app, event)

    # We only process update_checks in the update rpc.
    if not update_check:
      _Log('Non-update check received.  Returning blank payload')
      # TODO(sosa): Generate correct non-updatecheck payload to better test
      # update clients.
      return autoupdate_lib.GetNoUpdateResponse(protocol)

    # In case max_updates is used, return no response if max reached.
    if self.max_updates > 0:
      self.max_updates -= 1
    elif self.max_updates == 0:
      _Log('Request received but max number of updates handled')
      return autoupdate_lib.GetNoUpdateResponse(protocol)

    _Log('Update Check Received. Client is using protocol version: %s',
         protocol)

    if forced_update_label:
      if label:
        _Log('Label: %s set but being overwritten to %s by request', label,
             forced_update_label)

      label = forced_update_label

    # #########################################################################
    # Finally its time to generate the omaha response to give to client that
    # lets them know where to find the payload and its associated metadata.
    metadata_obj = None

    try:
      # Are we provisioning a remote or local payload?
      if self.remote_payload:
        # If no explicit label was provided, use the value of --payload.
        if not label:
          label = self.payload_path

        # Form the URL of the update payload. This assumes that the payload
        # file name is a devserver constant (which currently is the case).
        url = '/'.join(filter(None, [static_urlbase, label, UPDATE_FILE]))

        # Get remote payload attributes.
        metadata_obj = self._GetRemotePayloadAttrs(url)
      else:
        static_image_dir = _NonePathJoin(self.static_dir, label)
        rel_path = None

        # Serving files only, don't generate an update.
        if not self.serve_only:
          # Generate payload if necessary.
          rel_path = self.GenerateUpdatePayload(board, client_version,
                                                static_image_dir)

        url = '/'.join(filter(None, [static_urlbase, label, rel_path,
                                     UPDATE_FILE]))
        local_payload_dir = _NonePathJoin(static_image_dir, rel_path)
        metadata_obj = self.GetLocalPayloadAttrs(local_payload_dir)

    except AutoupdateError as e:
      # Raised if we fail to generate an update payload.
      _Log('Failed to process an update: %r', e)
      return autoupdate_lib.GetNoUpdateResponse(protocol)

    _Log('Responding to client to use url %s to get image', url)
    return autoupdate_lib.GetUpdateResponse(
        metadata_obj.sha1, metadata_obj.sha256, metadata_obj.size, url,
        metadata_obj.is_delta_format, protocol, self.critical_update)

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
