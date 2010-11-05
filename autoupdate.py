# Copyright (c) 2009-2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildutil import BuildObject
from xml.dom import minidom

import cherrypy
import os
import shutil
import socket
import time

def _LogMessage(message):
  cherrypy.log(message, 'UPDATE')


class Autoupdate(BuildObject):
  """Class that contains functionality that handles Chrome OS update pings.

  Members:
    serve_only: Serve images from a pre-built image.zip file.  static_dir
      must be set to the location of the image.zip.
    factory_config: Path to the factory config file if handling factory
      requests.
    use_test_image: Use chromiumos_test_image.bin rather than the standard.
    static_url_base: base URL, other than devserver, for update images.
    client_prefix: The prefix for the update engine client.
    forced_image: Path to an image to use for all updates.
  """

  def __init__(self, serve_only=None, test_image=False, urlbase=None,
               factory_config_path=None, client_prefix=None, forced_image=None,
               use_cached=False, port=8080, src_image='', vm=False, board=None,
               *args, **kwargs):
    super(Autoupdate, self).__init__(*args, **kwargs)
    self.serve_only = serve_only
    self.factory_config = factory_config_path
    self.use_test_image = test_image
    if urlbase:
      self.urlbase = urlbase
    else:
      self.urlbase = None

    self.client_prefix = client_prefix
    self.forced_image = forced_image
    self.use_cached = use_cached
    self.src_image = src_image
    self.vm = vm
    self.board = board

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
    """Returns true if the latest_version is greater than the client_version."""
    client_tokens = client_version.replace('_', '').split('.')
    latest_tokens = latest_version.replace('_', '').split('.')
    _LogMessage('client version %s latest version %s'
              % (client_version, latest_version))
    for i in range(4):
      if int(latest_tokens[i]) == int(client_tokens[i]):
        continue
      return int(latest_tokens[i]) > int(client_tokens[i])
    return False

  def _UnpackStatefulPartition(self, image_path, stateful_file):
    """Given an image, unpacks its stateful partition to stateful_file."""
    image_dir = os.path.dirname(image_path)
    image_file = os.path.basename(image_path)

    get_offset = '$(cgpt show -b -i 1 %s)' % image_file
    get_size = '$(cgpt show -s -i 1 %s)' % image_file
    unpack_command = (
        'cd %s && '
        'dd if=%s of=%s bs=512 skip=%s count=%s' % (image_dir, image_file,
                                                    stateful_file, get_offset,
                                                    get_size))
    _LogMessage(unpack_command)
    return os.system(unpack_command) == 0

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

  def _IsImageNewerThanCached(self, image_path, cached_file_path):
    """Returns true if the image is newer than the cached image."""
    if os.path.exists(cached_file_path) and os.path.exists(image_path):
      _LogMessage('Usable cached image found at %s.' % cached_file_path)
      return os.path.getmtime(image_path) > os.path.getmtime(cached_file_path)
    elif not os.path.exists(cached_file_path) and not os.path.exists(image_path):
      raise Exception('Image does not exist and cached image missing')
    else:
      # Only one is missing, figure out which one.
      if os.path.exists(image_path):
        _LogMessage('No cached image found - image generation required.')
        return True
      else:
        _LogMessage('Cached image found to serve at %s.' % cached_file_path)
        return False

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
    payload = """ < ?xml version = "1.0" encoding = "UTF-8"? >
      < gupdate xmlns = "http://www.google.com/update2/response" protocol = "2.0" >
        < daystart elapsed_seconds = "%s" />
        < app appid = "{%s}" status = "ok" >
          < ping status = "ok" />
          < updatecheck status = "noupdate" />
        </ app >
      </ gupdate >
    """
    return payload % (self._GetSecondsSinceMidnight(), self.app_id)

  def GenerateUpdateFile(self, image_path):
    """Generates an update gz given a full path to an image.

    Args:
      image_path: Full path to image.
    Returns:
      Path to created update_payload or None on error.
    """
    image_dir = os.path.dirname(image_path)
    update_path = os.path.join(image_dir, 'update.gz')
    patch_kernel_flag = '--patch_kernel'
    _LogMessage('Generating update image %s' % update_path)

    # Don't patch the kernel for vm images as they don't need the patch.
    if self.vm:
      patch_kernel_flag = ''

    mkupdate_command = (
        '%s/cros_generate_update_payload --image="%s" --output="%s" '
        '%s --noold_style --src_image="%s"' % (
            self.scripts_dir, image_path, update_path, patch_kernel_flag,
            self.src_image))
    _LogMessage(mkupdate_command)
    if os.system(mkupdate_command) != 0:
      _LogMessage('Failed to create base update file')
      return None

    return update_path

  def GenerateStatefulFile(self, image_path):
    """Generates a stateful update gz given a full path to an image.

    Args:
      image_path: Full path to image.
    Returns:
      Path to created stateful update_payload or None on error.
    """
    stateful_partition_path = '%s/stateful.image' % os.path.dirname(image_path)

    # Unpack to get stateful partition.
    if self._UnpackStatefulPartition(image_path, stateful_partition_path):
      mkstatefulupdate_command = 'gzip -f %s' % stateful_partition_path
      if os.system(mkstatefulupdate_command) == 0:
        _LogMessage('Successfully generated %s.gz' % stateful_partition_path)
        return '%s.gz' % stateful_partition_path

    _LogMessage('Failed to create stateful update file')
    return None

  def MoveImagesToStaticDir(self, update_path, stateful_update_path,
                            static_image_dir):
    """Moves gz files from their directories to serving directories.

    Args:
      update_path: full path to main update gz.
      stateful_update_path: full path to stateful partition gz.
      static_image_dir: where to put files.
    Returns:
      Returns True if the files were moved over successfully.
    """
    try:
      shutil.copy(update_path, static_image_dir)
      shutil.copy(stateful_update_path, static_image_dir)
      os.remove(update_path)
      os.remove(stateful_update_path)
    except Exception:
      _LogMessage('Failed to move %s and %s to %s' % (update_path,
                                                    stateful_update_path,
                                                    static_image_dir))
      return False

    return True

  def GenerateUpdateImage(self, image_path, move_to_static_dir=False,
                          static_image_dir=None):
    """Force generates an update payload based on the given image_path.

    Args:
      image_path: full path to the image.
      move_to_static_dir: Moves the files from their dir to the static dir.
      static_image_dir: the directory to move images to after generating.
    Returns:
      True if the update payload was created successfully.
    """
    _LogMessage('Generating update for image %s' % image_path)
    update_path = self.GenerateUpdateFile(image_path)
    if update_path:
      stateful_update_path = self.GenerateStatefulFile(image_path)
      if stateful_update_path:
        if move_to_static_dir:
          return self.MoveImagesToStaticDir(update_path, stateful_update_path,
                                            static_image_dir)

        return True

    _LogMessage('Failed to generate update')
    return False

  def GenerateLatestUpdateImage(self, board_id, client_version,
                                static_image_dir=None):
    """Generates an update using the latest image that has been built.

    This will only generate an update if the newest update is newer than that
    on the client or client_version is 'ForcedUpdate'.

    Args:
      board_id: Name of the board.
      client_version: Current version of the client or 'ForcedUpdate'
      static_image_dir: the directory to move images to after generating.
    Returns:
      True if the update payload was created successfully.
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
      return False

    cached_file_path = os.path.join(static_image_dir, 'update.gz')
    if (os.path.exists(cached_file_path) and
        not self._IsImageNewerThanCached(latest_image_path, cached_file_path)):
      return True

    return self.GenerateUpdateImage(latest_image_path, move_to_static_dir=True,
                                    static_image_dir=static_image_dir)

  def GenerateImageFromZip(self, static_image_dir):
    """Generates an update from an image zip file.

    This method assumes you have an image.zip in directory you are serving
    from.  If this file is newer than a previously cached file, it will unzip
    this file, create a payload and serve it.

    Args:
      static_image_dir: Directory where the zip file exists.
    Returns:
      True if the update payload was created successfully.
    """
    _LogMessage('Preparing to generate update from zip in %s.' % static_image_dir)
    image_path = os.path.join(static_image_dir, self._GetImageName())
    cached_file_path = os.path.join(static_image_dir, 'update.gz')
    zip_file_path = os.path.join(static_image_dir, 'image.zip')
    if not self._IsImageNewerThanCached(zip_file_path, cached_file_path):
      return True

    if not self._UnpackZip(static_image_dir):
      _LogMessage('unzip image.zip failed.')
      return False

    return self.GenerateUpdateImage(image_path, move_to_static_dir=False,
                                    static_image_dir=None)

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
    """Generates an update for non-factory and returns True on success."""
    if self.use_cached and os.path.exists(os.path.join(static_image_dir,
                                                       'update.gz')):
      _LogMessage('Using cached image regardless of timestamps.')
      return True
    else:
      if self.forced_image:
        has_built_image = self.GenerateUpdateImage(
            self.forced_image, move_to_static_dir=True,
            static_image_dir=static_image_dir)
        return has_built_image
      elif self.serve_only:
        return self.GenerateImageFromZip(static_image_dir)
      else:
        if board_id:
          return self.GenerateLatestUpdateImage(board_id,
                                                client_version,
                                                static_image_dir)

        _LogMessage('You must set --board for pre-generating latest update.')
        return False

  def PreGenerateUpdate(self):
    """Pre-generates an update.  Returns True on success."""
     # Does not work with factory config.
    assert(not self.factory_config)
    _LogMessage('Pre-generating the update payload.')
    # Does not work with labels so just use static dir.
    if self.GenerateUpdatePayloadForNonFactory(self.board, '0.0.0.0',
                                               self.static_dir):
      # Force the devserver to use the pre-generated payload.
      self.use_cached = True
      _LogMessage('Pre-generated update successfully.')
      return True
    else:
      _LogMessage('Failed to pre-generate update.')
      return False

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

    _LogMessage('Using static url base %s' % static_urlbase)
    _LogMessage('Handling update ping as %s: %s' % (self.hostname, data))

    # Check the client prefix to make sure you can support this type of update.
    update_dom = minidom.parseString(data)
    root = update_dom.firstChild
    if (root.hasAttribute('updaterversion') and
        not root.getAttribute('updaterversion').startswith(self.client_prefix)):
      _LogMessage('Got update from unsupported updater:' +
                root.getAttribute('updaterversion'))
      return self.GetNoUpdatePayload()

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

    # Separate logic as Factory requests have static url's that override
    # other options.
    if self.factory_config:
      return self.HandleFactoryRequest(board_id, channel)
    else:
      static_image_dir = self.static_dir
      if label:
        static_image_dir = os.path.join(static_image_dir, label)

      if self.GenerateUpdatePayloadForNonFactory(board_id, client_version,
                                                 static_image_dir):
        filename = os.path.join(static_image_dir, 'update.gz')
        hash = self._GetHash(filename)
        sha256 = self._GetSHA256(filename)
        size = self._GetSize(filename)
        is_delta_format = self._IsDeltaFormatFile(filename)
        if label:
          url = '%s/%s/update.gz' % (static_urlbase, label)
        else:
          url = '%s/update.gz' % static_urlbase

        _LogMessage('Responding to client to use url %s to get image.' % url)
        return self.GetUpdatePayload(hash, sha256, size, url, is_delta_format)
      else:
        return self.GetNoUpdatePayload()
