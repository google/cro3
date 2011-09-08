# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildutil import BuildObject
from xml.dom import minidom

import cherrypy
import json
import os
import shutil
import subprocess
import time
import urlparse


def _LogMessage(message):
  cherrypy.log(message, 'UPDATE')

UPDATE_FILE = 'update.gz'
STATEFUL_FILE = 'stateful.tgz'
CACHE_DIR = 'cache'


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


class Autoupdate(BuildObject):
  """Class that contains functionality that handles Chrome OS update pings.

  Members:
    serve_only: Serve only pre-built updates. static_dir must contain update.gz
      and stateful.tgz.
    factory_config: Path to the factory config file if handling factory
      requests.
    use_test_image: Use chromiumos_test_image.bin rather than the standard.
    static_url_base: base URL, other than devserver, for update images.
    forced_image: Path to an image to use for all updates.
    forced_payload: Path to pre-generated payload to serve.
    port: port to host devserver
    proxy_port: port of local proxy to tell client to connect to you through.
    src_image: If specified, creates a delta payload from this image.
    vm: Set for VM images (doesn't patch kernel)
    board: board for the image.  Needed for pre-generating of updates.
    copy_to_static_root: Copies images generated from the cache to
      ~/static.
  """

  def __init__(self, serve_only=None, test_image=False, urlbase=None,
               factory_config_path=None,
               forced_image=None, forced_payload=None,
               port=8080, proxy_port=None, src_image='', vm=False, board=None,
               copy_to_static_root=True, private_key=None,
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
    self.forced_payload = forced_payload
    self.src_image = src_image
    self.proxy_port = proxy_port
    self.vm = vm
    self.board = board
    self.copy_to_static_root = copy_to_static_root
    self.private_key = private_key

    # Path to pre-generated file.
    self.pregenerated_path = None

    # Initialize empty host info cache. Used to keep track of various bits of
    # information about a given host.
    self.host_info = {}

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
    return latest_version.split('-')[0]

  def _CanUpdate(self, client_version, latest_version):
    """Returns true if the latest_version is greater than the client_version.
    """
    client_tokens = client_version.replace('_', '').split('.')
    latest_tokens = latest_version.replace('_', '').split('.')
    _LogMessage('client version %s latest version %s'
                % (client_version, latest_version))
    for i in range(4):
      if int(latest_tokens[i]) == int(client_tokens[i]):
        continue
      return int(latest_tokens[i]) > int(client_tokens[i])
    return False

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

  def _GetSize(self, update_path):
    """Returns the size of the file given."""
    return os.path.getsize(update_path)

  def _GetHash(self, update_path):
    """Returns the sha1 of the file given."""
    cmd = ('cat %s | openssl sha1 -binary | openssl base64 | tr \'\\n\' \' \';'
           % update_path)
    return os.popen(cmd).read().rstrip()

  def _IsDeltaFormatFile(self, filename):
    try:
      file_handle = open(filename, 'r')
      delta_magic = 'CrAU'
      magic = file_handle.read(len(delta_magic))
      return magic == delta_magic
    except Exception:
      return False

  # TODO(petkov): Consider optimizing getting both SHA-1 and SHA-256 so that
  # it takes advantage of reduced I/O and multiple processors. Something like:
  # % tee < FILE > /dev/null \
  #     >( openssl dgst -sha256 -binary | openssl base64 ) \
  #     >( openssl sha1 -binary | openssl base64 )
  def _GetSHA256(self, update_path):
    """Returns the sha256 of the file given."""
    cmd = ('cat %s | openssl dgst -sha256 -binary | openssl base64' %
           update_path)
    return os.popen(cmd).read().rstrip()

  def _GetMd5(self, update_path):
    """Returns the md5 checksum of the file given."""
    cmd = ("md5sum %s | awk '{print $1}'" % update_path)
    return os.popen(cmd).read().rstrip()

  def _Copy(self, source, dest):
    """Copies a file from dest to source (if different)"""
    _LogMessage('Copy File %s -> %s' % (source, dest))
    if os.path.lexists(dest):
      os.remove(dest)
    shutil.copy(source, dest)

  def GetUpdatePayload(self, hash, sha256, size, url, is_delta_format):
    """Returns a payload to the client corresponding to a new update.

    Args:
      hash: hash of update blob
      sha256: SHA-256 hash of update blob
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
            codebase="%s"
            hash="%s"
            sha256="%s"
            needsadmin="false"
            size="%s"
            IsDelta="%s"
            status="ok"/>
        </app>
      </gupdate>
    """
    return payload % (self._GetSecondsSinceMidnight(),
                      self.app_id, url, hash, sha256, size, delta)

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
    _LogMessage('Generating update image %s' % update_path)

    update_command = [
        '%s/cros_generate_update_payload' % self.devserver_dir,
        '--image="%s"' % image_path,
        '--output="%s"' % update_path,
    ]

    if src_image: update_command.append('--src_image="%s"' % src_image)
    if not self.vm: update_command.append('--patch_kernel')
    if self.private_key: update_command.append('--private_key="%s"' %
                                               self.private_key)

    update_string = ' '.join(update_command)
    _LogMessage('Running ' + update_string)
    if os.system(update_string) != 0:
      _LogMessage('Failed to create update payload')
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
        ['%s/cros_generate_stateful_update_payload' % self.devserver_dir,
         '--image=%s' % image_path,
         '--output_dir=%s' % output_dir,
        ])
    return STATEFUL_FILE

  def FindCachedUpdateImageSubDir(self, src_image, dest_image):
    """Find directory to store a cached update.

    Given one, or two images for an update, this finds which
    cache directory should hold the update files, even if they don't exist
    yet. The directory will be inside static_image_dir, and of the form:

    Non-delta updates:
      CACHE_DIR/12345678
    Delta updates:
      CACHE_DIR/12345678_12345678

    If self.private_key -- Signed updates:
      CACHE_DIR/from_above+12345678
    """
    sub_dir = self._GetMd5(dest_image)
    if src_image:
      sub_dir = '%s_%s' % (self._GetMd5(src_image), sub_dir)

    if self.private_key:
      sub_dir = '%s+%s' % (sub_dir, self._GetMd5(self.private_key))

    return os.path.join(CACHE_DIR, sub_dir)

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
    _LogMessage('Generating update for image %s' % image_path)
    update_file = self.GenerateUpdateFile(self.src_image,
                                          image_path,
                                          output_dir)

    if update_file:
      stateful_update_file = self.GenerateStatefulFile(image_path,
                                                       output_dir)

    if update_file and stateful_update_file:
      return update_file
    else:
      _LogMessage('Failed to generate update.')
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
    _LogMessage('Generating update for src %s image %s' % (self.src_image,
                                                           image_path))

    # If it was pregenerated_path, don't regenerate
    if self.pregenerated_path:
      return self.pregenerated_path

    # Which sub_dir of static_image_dir should hold our cached update image
    cache_sub_dir = self.FindCachedUpdateImageSubDir(self.src_image, image_path)
    _LogMessage('Caching in sub_dir "%s"' % cache_sub_dir)

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
      self._Copy(cache_update_payload, update_payload)
      self._Copy(cache_stateful_payload, stateful_payload)
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

    _LogMessage('Preparing to generate update from latest built image %s.' %
              latest_image_path)

     # Check to see whether or not we should update.
    if client_version != 'ForcedUpdate' and not self._CanUpdate(
        client_version, latest_version):
      _LogMessage('no update')
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
          stanza[kind + '_size'] = self._GetSize(os.path.join(
              self.static_dir, stanza[kind + '_image']))
          if validate_checksums:
            factory_checksum = self._GetHash(os.path.join(self.static_dir,
                                             stanza[kind + '_image']))
            if factory_checksum != stanza[kind + '_checksum']:
              print ('Error: checksum mismatch for %s. Expected "%s" but file '
                     'has checksum "%s".' % (stanza[kind + '_image'],
                                             stanza[kind + '_checksum'],
                                             factory_checksum))
              success = False

    if validate_checksums:
      if success is False:
        raise Exception('Checksum mismatch in conf file.')

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
    return (None, None, None)

  def HandleFactoryRequest(self, board_id, channel):
    (filename, checksum, size) = self.GetFactoryImage(board_id, channel)
    if filename is None:
      _LogMessage('unable to find image for board %s' % board_id)
      return self.GetNoUpdatePayload()
    url = '%s/static/%s' % (self.hostname, filename)
    is_delta_format = self._IsDeltaFormatFile(filename)
    _LogMessage('returning update payload ' + url)
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

    if self.forced_payload:
      # If the forced payload is not already in our static_image_dir,
      # copy it there.
      src_path = os.path.abspath(self.forced_payload)
      src_stateful = os.path.join(os.path.dirname(src_path),
                                  STATEFUL_FILE)

      # Only copy the files if the source directory is different from dest.
      if os.path.dirname(src_path) != os.path.abspath(static_image_dir):
        self._Copy(src_path, dest_path)

        # The stateful payload is optional.
        if os.path.exists(src_stateful):
          self._Copy(src_stateful, dest_stateful)
        else:
          _LogMessage('WARN: %s not found. Expected for dev and test builds.' %
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
        _LogMessage('WARN: %s not found. Expected for dev and test builds.' %
                    UPDATE_FILE)

      if not os.path.exists(dest_stateful):
        _LogMessage('WARN: %s not found. Expected for dev and test builds.' %
                    STATEFUL_FILE)

      return UPDATE_FILE
    else:
      if board_id:
        return self.GenerateLatestUpdateImage(board_id,
                                              client_version,
                                              static_image_dir)

      _LogMessage('Failed to genereate update. '
                  'You must set --board when pre-generating latest update.')
      return None

  def PreGenerateUpdate(self):
    """Pre-generates an update and prints out the relative path it.

    Returns relative path of the update on success.
    """
     # Does not work with factory config.
    assert(not self.factory_config)
    _LogMessage('Pre-generating the update payload.')
    # Does not work with labels so just use static dir.
    pregenerated_update = self.GenerateUpdatePayloadForNonFactory(
        self.board, '0.0.0.0', self.static_dir)
    if pregenerated_update:
      print 'PREGENERATED_UPDATE=%s' % pregenerated_update

    return pregenerated_update

  def HandleUpdatePing(self, data, label=None):
    """Handles an update ping from an update client.

    Args:
      data: xml blob from client.
      label: optional label for the update.
    Returns:
      Update payload message for client.
    """
    # Set hostname as the hostname that the client is calling to and set up
    # the url base.
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

    _LogMessage('Using static url base %s' % static_urlbase)
    _LogMessage('Handling update ping as %s: %s' % (self.hostname, data))

    update_dom = minidom.parseString(data)
    root = update_dom.firstChild

    # Determine request IP, strip any IPv6 data for simplicity.
    client_ip = cherrypy.request.remote.ip.split(':')[-1]

    # Initialize host info dictionary for this client if it doesn't exist.
    self.host_info.setdefault(client_ip, {})

    # Store event details in the host info dictionary for API usage.
    event = root.getElementsByTagName('o:event')
    if event:
      self.host_info[client_ip]['last_event_status'] = (
          int(event[0].getAttribute('eventresult')))
      self.host_info[client_ip]['last_event_type'] = (
          int(event[0].getAttribute('eventtype')))

    # We only generate update payloads for updatecheck requests.
    update_check = root.getElementsByTagName('o:updatecheck')
    if not update_check:
      _LogMessage('Non-update check received.  Returning blank payload.')
      # TODO(sosa): Generate correct non-updatecheck payload to better test
      # update clients.
      return self.GetNoUpdatePayload()

    # Since this is an updatecheck, get information about the requester.
    query = root.getElementsByTagName('o:app')[0]
    client_version = query.getAttribute('version')
    channel = query.getAttribute('track')
    board_id = (query.hasAttribute('board') and query.getAttribute('board')
                or self._GetDefaultBoardID())

    # Store version for this host in the cache.
    self.host_info[client_ip]['last_known_version'] = client_version

    # Check if an update has been forced for this client.
    forced_update = self.host_info[client_ip].pop('forced_update_label', None)
    if forced_update:
      label = forced_update

    # Separate logic as Factory requests have static url's that override
    # other options.
    if self.factory_config:
      return self.HandleFactoryRequest(board_id, channel)
    else:
      static_image_dir = self.static_dir
      if label:
        static_image_dir = os.path.join(static_image_dir, label)

      payload_path = self.GenerateUpdatePayloadForNonFactory(board_id,
                                                             client_version,
                                                             static_image_dir)
      if payload_path:
        filename = os.path.join(static_image_dir, payload_path)
        hash = self._GetHash(filename)
        sha256 = self._GetSHA256(filename)
        size = self._GetSize(filename)
        is_delta_format = self._IsDeltaFormatFile(filename)
        if label:
          url = '%s/%s/%s' % (static_urlbase, label, payload_path)
        else:
          url = '%s/%s' % (static_urlbase, payload_path)

        _LogMessage('Responding to client to use url %s to get image.' % url)
        return self.GetUpdatePayload(hash, sha256, size, url, is_delta_format)
      else:
        return self.GetNoUpdatePayload()

  def HandleHostInfoPing(self, ip):
    """Returns host info dictionary for the given IP in JSON format."""
    assert ip, 'No ip provided.'
    if ip in self.host_info:
      return json.dumps(self.host_info[ip])

  def HandleSetUpdatePing(self, ip, label):
    """Sets forced_update_label for a given host."""
    assert ip, 'No ip provided.'
    assert label, 'No label provided.'
    self.host_info.setdefault(ip, {})['forced_update_label'] = label
