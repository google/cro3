# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from xml.dom import minidom
import datetime
import json
import os
import shutil
import subprocess
import time
import urllib2
import urlparse

import cherrypy

from build_util import BuildObject
import common_util
import log_util


# Module-local log function.
def _Log(message, *args, **kwargs):
  return log_util.LogWithTag('UPDATE', message, *args, **kwargs)


UPDATE_FILE = 'update.gz'
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


class HostInfo:
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

  def SetAttr(self, attr, value):
    """Set an attribute value."""
    self.attrs[attr] = value

  def GetAttr(self, attr):
    """Returns the value of an attribute."""
    if attr in self.attrs:
      return self.attrs[attr]

  def PopAttr(self, attr, default):
    """Returns and deletes a particular attribute."""
    return self.attrs.pop(attr, default)


class HostInfoTable:
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
    if host_id in self.table:
      return self.table[host_id]


class Autoupdate(BuildObject):
  """Class that contains functionality that handles Chrome OS update pings.

  Members:
    serve_only:      serve only pre-built updates. static_dir must contain
                     update.gz and stateful.tgz.
    factory_config:  path to the factory config file if handling factory
                     requests.
    use_test_image:  use chromiumos_test_image.bin rather than the standard.
    urlbase:         base URL, other than devserver, for update images.
    forced_image:    path to an image to use for all updates.
    payload_path:    path to pre-generated payload to serve.
    src_image:       if specified, creates a delta payload from this image.
    proxy_port:      port of local proxy to tell client to connect to you
                     through.
    vm:              set for VM images (doesn't patch kernel)
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

  def __init__(self, serve_only=None, test_image=False, urlbase=None,
               factory_config_path=None,
               forced_image=None, payload_path=None,
               proxy_port=None, src_image='', vm=False, board=None,
               copy_to_static_root=True, private_key=None,
               critical_update=False, remote_payload=False, max_updates=-1,
               host_log=False,
               *args, **kwargs):
    super(Autoupdate, self).__init__(*args, **kwargs)
    self.serve_only = serve_only
    self.factory_config = factory_config_path
    self.use_test_image = test_image
    if urlbase:
      self.urlbase = urlbase
    else:
      self.urlbase = None

    self.forced_image = forced_image
    self.payload_path = payload_path
    self.src_image = src_image
    self.proxy_port = proxy_port
    self.vm = vm
    self.board = board
    self.copy_to_static_root = copy_to_static_root
    self.private_key = private_key
    self.critical_update = critical_update
    self.remote_payload = remote_payload
    self.max_updates=max_updates
    self.host_log = host_log

    # Path to pre-generated file.
    self.pregenerated_path = None

    # Initialize empty host info cache. Used to keep track of various bits of
    # information about a given host.  A host is identified by its IP address.
    # The info stored for each host includes a complete log of events for this
    # host, as well as a dictionary of current attributes derived from events.
    self.host_infos = HostInfoTable()

  def _GetSecondsSinceMidnight(self):
    """Returns the seconds since midnight as a decimal value."""
    now = time.localtime()
    return now[3] * 3600 + now[4] * 60 + now[5]

  def _GetDefaultBoardID(self):
    """Returns the default board id stored in .default_board."""
    board_file = '%s/.default_board' % (self.scripts_dir)
    try:
      return open(board_file).read()
    except IOError:
      return 'x86-generic'

  def _GetLatestImageDir(self, board_id):
    """Returns the latest image dir based on shell script."""
    cmd = '%s/get_latest_image.sh --board %s' % (self.scripts_dir, board_id)
    return os.popen(cmd).read().strip()

  def _GetVersionFromDir(self, image_dir):
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

  def _CanUpdate(self, client_version, latest_version):
    """Returns true if the latest_version is greater than the client_version.
    """
    _Log('client version %s latest version %s'
         % (client_version, latest_version))

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

  def _UnpackZip(self, image_dir):
    """Unpacks an image.zip into a given directory."""
    image = os.path.join(image_dir, self._GetImageName())
    if os.path.exists(image):
      return True
    else:
      # -n, never clobber an existing file, in case we get invoked
      # simultaneously by multiple request handlers. This means that
      # we're assuming each image.zip file lives in a versioned
      # directory (a la Buildbot).
      return os.system('cd %s && unzip -n image.zip' % image_dir) == 0

  def _GetImageName(self):
    """Returns the name of the image that should be used."""
    if self.use_test_image:
      image_name = 'chromiumos_test_image.bin'
    else:
      image_name = 'chromiumos_image.bin'
    return image_name

  def _IsDeltaFormatFile(self, filename):
    try:
      file_handle = open(filename, 'r')
      delta_magic = 'CrAU'
      magic = file_handle.read(len(delta_magic))
      return magic == delta_magic
    except Exception:
      return False

  def GetUpdatePayload(self, sha1, sha256, size, url, is_delta_format):
    """Returns a payload to the client corresponding to a new update.

    Args:
      sha1: SHA1 hash of update blob
      sha256: SHA256 hash of update blob
      size: size of update blob
      url: where to find update blob
    Returns:
      Xml string to be passed back to client.
    """
    delta = 'false'
    if is_delta_format:
      delta = 'true'
    payload = """<?xml version="1.0" encoding="UTF-8"?>
      <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
        <daystart elapsed_seconds="%s"/>
        <app appid="{%s}" status="ok">
          <ping status="ok"/>
          <updatecheck
            ChromeOSVersion="9999.0.0"
            codebase="%s"
            hash="%s"
            sha256="%s"
            needsadmin="false"
            size="%s"
            IsDelta="%s"
            status="ok"
            %s/>
        </app>
      </gupdate>
    """
    extra_attributes = []
    if self.critical_update:
      # The date string looks like '20111115' (2011-11-15). As of writing,
      # there's no particular format for the deadline value that the
      # client expects -- it's just empty vs. non-empty.
      date_str = datetime.date.today().strftime('%Y%m%d')
      extra_attributes.append('deadline="%s"' % date_str)
    xml = payload % (self._GetSecondsSinceMidnight(),
                     self.app_id, url, sha1, sha256, size, delta,
                     ' '.join(extra_attributes))
    _Log('Generated update payload: %s' % xml)
    return xml

  def GetNoUpdatePayload(self):
    """Returns a payload to the client corresponding to no update."""
    payload = """<?xml version="1.0" encoding="UTF-8"?>
      <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
        <daystart elapsed_seconds="%s"/>
        <app appid="{%s}" status="ok">
          <ping status="ok"/>
          <updatecheck status="noupdate"/>
        </app>
      </gupdate>
    """
    return payload % (self._GetSecondsSinceMidnight(), self.app_id)

  def GenerateUpdateFile(self, src_image, image_path, output_dir):
    """Generates an update gz given a full path to an image.

    Args:
      image_path: Full path to image.
    Returns:
      Path to created update_payload or None on error.
    """
    update_path = os.path.join(output_dir, UPDATE_FILE)
    _Log('Generating update image %s' % update_path)

    update_command = [
        'cros_generate_update_payload',
        '--image="%s"' % image_path,
        '--output="%s"' % update_path,
    ]

    if src_image: update_command.append('--src_image="%s"' % src_image)
    if not self.vm: update_command.append('--patch_kernel')
    if self.private_key: update_command.append('--private_key="%s"' %
                                               self.private_key)

    update_string = ' '.join(update_command)
    _Log('Running ' + update_string)
    if os.system(update_string) != 0:
      _Log('Failed to create update payload')
      return None

    return UPDATE_FILE

  def GenerateStatefulFile(self, image_path, output_dir):
    """Generates a stateful update payload given a full path to an image.

    Args:
      image_path: Full path to image.
    Returns:
      Path to created stateful update_payload or None on error.
    Raises:
      A subprocess exception if the update generator fails to generate a
      stateful payload.
    """
    output_gz = os.path.join(output_dir, STATEFUL_FILE)
    subprocess.check_call(
        ['cros_generate_stateful_update_payload',
         '--image=%s' % image_path,
         '--output_dir=%s' % output_dir,
        ])
    return STATEFUL_FILE

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

    if not self.vm:
      update_dir += '+patched_kernel'

    return os.path.join(CACHE_DIR, update_dir)

  def GenerateUpdateImage(self, image_path, output_dir):
    """Force generates an update payload based on the given image_path.

    Args:
      src_image: image we are updating from (Null/empty for non-delta)
      image_path: full path to the image.
      output_dir: the directory to write the update payloads in
    Returns:
      update payload name relative to output_dir
    """
    update_file = None
    stateful_update_file = None

    # Actually do the generation
    _Log('Generating update for image %s' % image_path)
    update_file = self.GenerateUpdateFile(self.src_image,
                                          image_path,
                                          output_dir)

    if update_file:
      stateful_update_file = self.GenerateStatefulFile(image_path,
                                                       output_dir)

    if update_file and stateful_update_file:
      return update_file
    else:
      _Log('Failed to generate update.')
      return None

  def GenerateUpdateImageWithCache(self, image_path, static_image_dir):
    """Force generates an update payload based on the given image_path.

    Args:
      image_path: full path to the image.
      static_image_dir: the directory to move images to after generating.
    Returns:
      update filename (not directory) relative to static_image_dir on success,
        or None.
    """
    _Log('Generating update for src %s image %s' % (self.src_image, image_path))

    # If it was pregenerated_path, don't regenerate
    if self.pregenerated_path:
      return self.pregenerated_path

    # Which sub_dir of static_image_dir should hold our cached update image
    cache_sub_dir = self.FindCachedUpdateImageSubDir(self.src_image, image_path)
    _Log('Caching in sub_dir "%s"' % cache_sub_dir)

    update_path = os.path.join(cache_sub_dir, UPDATE_FILE)

    # The cached payloads exist in a cache dir
    cache_update_payload = os.path.join(static_image_dir,
                                        update_path)
    cache_stateful_payload = os.path.join(static_image_dir,
                                          cache_sub_dir,
                                          STATEFUL_FILE)

    # Check to see if this cache directory is valid.
    if not os.path.exists(cache_update_payload) or not os.path.exists(
        cache_stateful_payload):
      full_cache_dir = os.path.join(static_image_dir, cache_sub_dir)
      # Clean up stale state.
      os.system('rm -rf "%s"' % full_cache_dir)
      os.makedirs(full_cache_dir)
      return_path = self.GenerateUpdateImage(image_path,
                                             full_cache_dir)

      # Clean up cache dir since it's not valid.
      if not return_path:
        os.system('rm -rf "%s"' % full_cache_dir)
        return None

    self.pregenerated_path = update_path

    # Generation complete, copy if requested.
    if self.copy_to_static_root:
      # The final results exist directly in static
      update_payload = os.path.join(static_image_dir,
                                    UPDATE_FILE)
      stateful_payload = os.path.join(static_image_dir,
                                      STATEFUL_FILE)
      common_util.CopyFile(cache_update_payload, update_payload)
      common_util.CopyFile(cache_stateful_payload, stateful_payload)
      return UPDATE_FILE
    else:
      return self.pregenerated_path

  def GenerateLatestUpdateImage(self, board_id, client_version,
                                static_image_dir):
    """Generates an update using the latest image that has been built.

    This will only generate an update if the newest update is newer than that
    on the client or client_version is 'ForcedUpdate'.

    Args:
      board_id: Name of the board.
      client_version: Current version of the client or 'ForcedUpdate'
      static_image_dir: the directory to move images to after generating.
    Returns:
      Name of the update image relative to static_image_dir or None
    """
    latest_image_dir = self._GetLatestImageDir(board_id)
    latest_version = self._GetVersionFromDir(latest_image_dir)
    latest_image_path = os.path.join(latest_image_dir, self._GetImageName())

    _Log('Preparing to generate update from latest built image %s.' %
         latest_image_path)

     # Check to see whether or not we should update.
    if client_version != 'ForcedUpdate' and not self._CanUpdate(
        client_version, latest_version):
      _Log('no update')
      return None

    return self.GenerateUpdateImageWithCache(latest_image_path,
                                             static_image_dir=static_image_dir)

  def ImportFactoryConfigFile(self, filename, validate_checksums=False):
    """Imports a factory-floor server configuration file. The file should
    be in this format:
      config = [
        {
          'qual_ids': set([1, 2, 3, "x86-generic"]),
          'factory_image': 'generic-factory.gz',
          'factory_checksum': 'AtiI8B64agHVN+yeBAyiNMX3+HM=',
          'release_image': 'generic-release.gz',
          'release_checksum': 'AtiI8B64agHVN+yeBAyiNMX3+HM=',
          'oempartitionimg_image': 'generic-oem.gz',
          'oempartitionimg_checksum': 'AtiI8B64agHVN+yeBAyiNMX3+HM=',
          'efipartitionimg_image': 'generic-efi.gz',
          'efipartitionimg_checksum': 'AtiI8B64agHVN+yeBAyiNMX3+HM=',
          'stateimg_image': 'generic-state.gz',
          'stateimg_checksum': 'AtiI8B64agHVN+yeBAyiNMX3+HM=',
          'firmware_image': 'generic-firmware.gz',
          'firmware_checksum': 'AtiI8B64agHVN+yeBAyiNMX3+HM=',
        },
        {
          'qual_ids': set([6]),
          'factory_image': '6-factory.gz',
          'factory_checksum': 'AtiI8B64agHVN+yeBAyiNMX3+HM=',
          'release_image': '6-release.gz',
          'release_checksum': 'AtiI8B64agHVN+yeBAyiNMX3+HM=',
          'oempartitionimg_image': '6-oem.gz',
          'oempartitionimg_checksum': 'AtiI8B64agHVN+yeBAyiNMX3+HM=',
          'efipartitionimg_image': '6-efi.gz',
          'efipartitionimg_checksum': 'AtiI8B64agHVN+yeBAyiNMX3+HM=',
          'stateimg_image': '6-state.gz',
          'stateimg_checksum': 'AtiI8B64agHVN+yeBAyiNMX3+HM=',
          'firmware_image': '6-firmware.gz',
          'firmware_checksum': 'AtiI8B64agHVN+yeBAyiNMX3+HM=',
        },
      ]
    The server will look for the files by name in the static files
    directory.

    If validate_checksums is True, validates checksums and exits. If
    a checksum mismatch is found, it's printed to the screen.
    """
    f = open(filename, 'r')
    output = {}
    exec(f.read(), output)
    self.factory_config = output['config']
    success = True
    for stanza in self.factory_config:
      for key in stanza.copy().iterkeys():
        suffix = '_image'
        if key.endswith(suffix):
          kind = key[:-len(suffix)]
          stanza[kind + '_size'] = common_util.GetFileSize(os.path.join(
              self.static_dir, stanza[kind + '_image']))
          if validate_checksums:
            factory_checksum = common_util.GetFileSha1(
                os.path.join(self.static_dir, stanza[kind + '_image']))
            if factory_checksum != stanza[kind + '_checksum']:
              print ('Error: checksum mismatch for %s. Expected "%s" but file '
                     'has checksum "%s".' % (stanza[kind + '_image'],
                                             stanza[kind + '_checksum'],
                                             factory_checksum))
              success = False

    if validate_checksums:
      if success is False:
        raise AutoupdateError('Checksum mismatch in conf file.')

      print 'Config file looks good.'

  def GetFactoryImage(self, board_id, channel):
    kind = channel.rsplit('-', 1)[0]
    for stanza in self.factory_config:
      if board_id not in stanza['qual_ids']:
        continue
      if kind + '_image' not in stanza:
        break
      return (stanza[kind + '_image'],
              stanza[kind + '_checksum'],
              stanza[kind + '_size'])
    return None, None, None

  def HandleFactoryRequest(self, board_id, channel):
    (filename, checksum, size) = self.GetFactoryImage(board_id, channel)
    if filename is None:
      _Log('unable to find image for board %s' % board_id)
      return self.GetNoUpdatePayload()
    url = '%s/static/%s' % (self.hostname, filename)
    is_delta_format = self._IsDeltaFormatFile(filename)
    _Log('returning update payload ' + url)
    # Factory install is using memento updater which is using the sha-1 hash so
    # setting sha-256 to an empty string.
    return self.GetUpdatePayload(checksum, '', size, url, is_delta_format)

  def GenerateUpdatePayloadForNonFactory(self, board_id, client_version,
                                         static_image_dir):
    """Generates an update for non-factory image.

       Returns:
         file name relative to static_image_dir on success.
    """
    dest_path = os.path.join(static_image_dir, UPDATE_FILE)
    dest_stateful = os.path.join(static_image_dir, STATEFUL_FILE)

    if self.payload_path:
      # If the forced payload is not already in our static_image_dir,
      # copy it there.
      src_path = os.path.abspath(self.payload_path)
      src_stateful = os.path.join(os.path.dirname(src_path),
                                  STATEFUL_FILE)

      # Only copy the files if the source directory is different from dest.
      if os.path.dirname(src_path) != os.path.abspath(static_image_dir):
        common_util.CopyFile(src_path, dest_path)

        # The stateful payload is optional.
        if os.path.exists(src_stateful):
          common_util.CopyFile(src_stateful, dest_stateful)
        else:
          _Log('WARN: %s not found. Expected for dev and test builds.' %
               STATEFUL_FILE)
          if os.path.exists(dest_stateful):
            os.remove(dest_stateful)

      return UPDATE_FILE
    elif self.forced_image:
      return self.GenerateUpdateImageWithCache(
          self.forced_image,
          static_image_dir=static_image_dir)
    elif self.serve_only:
      # Warn if update or stateful files can't be found.
      if not os.path.exists(dest_path):
        _Log('WARN: %s not found. Expected for dev and test builds.' %
             UPDATE_FILE)

      if not os.path.exists(dest_stateful):
        _Log('WARN: %s not found. Expected for dev and test builds.' %
             STATEFUL_FILE)

      return UPDATE_FILE
    else:
      if board_id:
        return self.GenerateLatestUpdateImage(board_id,
                                              client_version,
                                              static_image_dir)

      _Log('Failed to genereate update. '
           'You must set --board when pre-generating latest update.')
      return None

  def PreGenerateUpdate(self):
    """Pre-generates an update and prints out the relative path it.

    Returns relative path of the update on success.
    """
     # Does not work with factory config.
    assert(not self.factory_config)
    _Log('Pre-generating the update payload.')
    # Does not work with labels so just use static dir.
    pregenerated_update = self.GenerateUpdatePayloadForNonFactory(
        self.board, '0.0.0.0', self.static_dir)
    if pregenerated_update:
      print 'PREGENERATED_UPDATE=%s' % pregenerated_update

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
    _Log('retrieving file info for remote payload via %s' % fileinfo_url)
    try:
      conn = urllib2.urlopen(fileinfo_url)
      file_attr_dict = json.loads(conn.read())
      sha1 = file_attr_dict['sha1']
      sha256 = file_attr_dict['sha256']
      size = file_attr_dict['size']
    except Exception, e:
      _Log('failed to obtain remote payload info: %s' % str(e))
      raise
    is_delta_format = ('_mton' in url) or ('_nton' in url)

    return sha1, sha256, size, is_delta_format

  def _GetLocalPayloadAttrs(self, static_image_dir, payload_path):
    """Returns hashes, size and delta flag of a local update payload.

    Args:
      static_image_dir: directory where static files are being staged
      payload_path: path to the payload file inside the static directory
    Returns:
      A tuple containing the SHA1, SHA256, file size and whether or not it's a
      delta payload (Boolean).
    """
    filename = os.path.join(static_image_dir, payload_path)
    sha1 = common_util.GetFileSha1(filename)
    sha256 = common_util.GetFileSha256(filename)
    size = common_util.GetFileSize(filename)
    is_delta_format = self._IsDeltaFormatFile(filename)
    return sha1, sha256, size, is_delta_format

  def HandleUpdatePing(self, data, label=None):
    """Handles an update ping from an update client.

    Args:
      data: xml blob from client.
      label: optional label for the update.
    Returns:
      Update payload message for client.
    """
    # Set hostname as the hostname that the client is calling to and set up
    # the url base. If behind apache mod_proxy | mod_rewrite, the hostname will
    # be in X-Forwarded-Host.
    x_forwarded_host = cherrypy.request.headers.get('X-Forwarded-Host')
    if x_forwarded_host:
      self.hostname = 'http://' + x_forwarded_host
    else:
      self.hostname = cherrypy.request.base

    if self.urlbase:
      static_urlbase = self.urlbase
    elif self.serve_only:
      static_urlbase = '%s/static/archive' % self.hostname
    else:
      static_urlbase = '%s/static' % self.hostname

    # If we have a proxy port, adjust the URL we instruct the client to
    # use to go through the proxy.
    if self.proxy_port:
      static_urlbase = _ChangeUrlPort(static_urlbase, self.proxy_port)

    _Log('Using static url base %s' % static_urlbase)
    _Log('Handling update ping as %s: %s' % (self.hostname, data))

    update_dom = minidom.parseString(data)
    root = update_dom.firstChild

    # Determine request IP, strip any IPv6 data for simplicity.
    client_ip = cherrypy.request.remote.ip.split(':')[-1]

    # Obtain (or init) info object for this client.
    curr_host_info = self.host_infos.GetInitHostInfo(client_ip)

    # Initialize an empty dictionary for event attributes.
    log_message = {}

    # Store event details in the host info dictionary for API usage.
    event = root.getElementsByTagName('o:event')
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

    # Get information about the requester.
    query = root.getElementsByTagName('o:app')[0]
    if query:
      client_version = query.getAttribute('version')
      channel = query.getAttribute('track')
      board_id = (query.hasAttribute('board') and query.getAttribute('board')
          or self._GetDefaultBoardID())
      # Add attributes to log message
      log_message['version'] = client_version
      log_message['track'] = channel
      log_message['board'] = board_id

    # Log host event, if so instructed.
    if self.host_log:
      curr_host_info.AddLogEntry(log_message)

    # We only generate update payloads for updatecheck requests.
    update_check = root.getElementsByTagName('o:updatecheck')
    if not update_check:
      _Log('Non-update check received.  Returning blank payload.')
      # TODO(sosa): Generate correct non-updatecheck payload to better test
      # update clients.
      return self.GetNoUpdatePayload()

    # Store version for this host in the cache.
    curr_host_info.attrs['last_known_version'] = client_version

    # If maximum number of updates already requested, refuse.
    if self.max_updates > 0:
      self.max_updates -= 1
    elif self.max_updates == 0:
      return self.GetNoUpdatePayload()

    # Check if an update has been forced for this client.
    forced_update = curr_host_info.PopAttr('forced_update_label', None)
    if forced_update:
      label = forced_update

    # Separate logic as Factory requests have static url's that override
    # other options.
    if self.factory_config:
      return self.HandleFactoryRequest(board_id, channel)
    else:
      url = ''
      # Are we provisioning a remote or local payload?
      if self.remote_payload:
        # If no explicit label was provided, use the value of --payload.
        if not label and self.payload_path:
          label = self.payload_path

        # Form the URL of the update payload. This assumes that the payload
        # file name is a devserver constant (which currently is the case).
        url = '/'.join(filter(None, [static_urlbase, label, UPDATE_FILE]))

        # Get remote payload attributes.
        sha1, sha256, file_size, is_delta_format = \
            self._GetRemotePayloadAttrs(url)
      else:
        # Generate payload.
        static_image_dir = os.path.join(*filter(None, [self.static_dir, label]))
        payload_path = self.GenerateUpdatePayloadForNonFactory(
            board_id, client_version, static_image_dir)
        # If properly generated, obtain the payload URL and attributes.
        if payload_path:
          url = '/'.join(filter(None, [static_urlbase, label, payload_path]))
          sha1, sha256, file_size, is_delta_format = \
              self._GetLocalPayloadAttrs(static_image_dir, payload_path)

      # If we end up with an actual payload path, generate a response.
      if url:
        _Log('Responding to client to use url %s to get image.' % url)
        return self.GetUpdatePayload(
            sha1, sha256, file_size, url, is_delta_format)
      else:
        return self.GetNoUpdatePayload()

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
