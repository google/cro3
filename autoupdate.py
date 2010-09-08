# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildutil import BuildObject
from xml.dom import minidom

import os
import shutil
import sys
import time
import web

class Autoupdate(BuildObject):
  # Basic functionality of handling ChromeOS autoupdate pings
  # and building/serving update images.
  # TODO(rtc): Clean this code up and write some tests.

  def __init__(self, serve_only=None, test_image=False, urlbase=None,
               factory_config_path=None, validate_factory_config=None,
               client_prefix=None,
               *args, **kwargs):
    super(Autoupdate, self).__init__(*args, **kwargs)
    self.serve_only = serve_only
    self.factory_config = factory_config_path
    self.test_image = test_image
    self.static_urlbase = urlbase
    self.client_prefix = client_prefix
    if serve_only:
      # If  we're  serving  out  of  an archived  build  dir  (e.g.  a
      # buildbot), prepare this webserver's magic 'static/' dir with a
      # link to the build archive.
      web.debug('Autoupdate in "serve update images only" mode.')
      if os.path.exists('static/archive'):
        if self.static_dir != os.readlink('static/archive'):
          web.debug('removing stale symlink to %s' % self.static_dir)
          os.unlink('static/archive')
          os.symlink(self.static_dir, 'static/archive')
      else:
         os.symlink(self.static_dir, 'static/archive')
    if factory_config_path is not None:
      self.ImportFactoryConfigFile(factory_config_path, validate_factory_config)

  def GetSecondsSinceMidnight(self):
    now = time.localtime()
    return now[3] * 3600 + now[4] * 60 + now[5]

  def GetUpdatePayload(self, hash, size, url):
    payload = """<?xml version="1.0" encoding="UTF-8"?>
      <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
        <daystart elapsed_seconds="%s"/>
        <app appid="{%s}" status="ok">
          <ping status="ok"/>
          <updatecheck
            codebase="%s"
            hash="%s"
            needsadmin="false"
            size="%s"
            status="ok"/>
        </app>
      </gupdate>
    """
    return payload % (self.GetSecondsSinceMidnight(),
                      self.app_id, url, hash, size)

  def GetNoUpdatePayload(self):
    payload = """<?xml version="1.0" encoding="UTF-8"?>
      <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
        <daystart elapsed_seconds="%s"/>
        <app appid="{%s}" status="ok">
          <ping status="ok"/>
          <updatecheck status="noupdate"/>
        </app>
      </gupdate>
    """
    return payload % (self.GetSecondsSinceMidnight(), self.app_id)

  def GetDefaultBoardID(self):
    board_file = '%s/.default_board' % (self.scripts_dir)
    try:
      return open(board_file).read()
    except IOError:
      return 'x86-generic'

  def GetLatestImagePath(self, board_id):
    cmd = '%s/get_latest_image.sh --board %s' % (self.scripts_dir, board_id)
    return os.popen(cmd).read().strip()

  def GetLatestVersion(self, latest_image_path):
    latest_version = latest_image_path.split('/')[-1]

    # Removes the portage build prefix.
    latest_version = latest_version.lstrip('g-')
    return latest_version.split('-')[0]

  def CanUpdate(self, client_version, latest_version):
    """
      Returns true iff the latest_version is greater than the client_version.
    """
    client_tokens = client_version.replace('_', '').split('.')
    latest_tokens = latest_version.replace('_', '').split('.')
    web.debug('client version %s latest version %s' \
        % (client_version, latest_version))
    for i in range(4):
      if int(latest_tokens[i]) == int(client_tokens[i]):
        continue
      return int(latest_tokens[i]) > int(client_tokens[i])
    return False

  def UnpackStatefulPartition(self, image_path, image_file, stateful_file):
    """Given an image, unpacks the stateful partition to stateful_file."""
    get_offset = '$(cgpt show -b -i 1 %s)' % image_file
    get_size = '$(cgpt show -s -i 1 %s)' % image_file
    unpack_command = (
        'cd %s && '
        'dd if=%s of=%s bs=512 skip=%s count=%s' % (image_path, image_file,
            stateful_file, get_offset, get_size))
    web.debug(unpack_command)
    return os.system(unpack_command) == 0

  def UnpackZip(self, image_path, image_file):
    image = os.path.join(image_path, image_file)
    if os.path.exists(image):
      return True
    else:
      # -n, never clobber an existing file, in case we get invoked
      # simultaneously by multiple request handlers. This means that
      # we're assuming each image.zip file lives in a versioned
      # directory (a la Buildbot).
      return os.system('cd %s && unzip -n image.zip %s unpack_partitions.sh' %
                       (image_path, image_file)) == 0

  def GetImageBinPath(self, image_path):
    if self.test_image:
      image_file = 'chromiumos_test_image.bin'
    else:
      image_file = 'chromiumos_image.bin'
    return image_file

  def BuildUpdateImage(self, image_path):
    stateful_file = '%s/stateful.image' % image_path
    image_file = self.GetImageBinPath(image_path)
    bin_path = os.path.join(image_path, image_file)

    # Get appropriate update.gz to compare timestamps.
    if self.serve_only:
      cached_update_file = os.path.join(image_path, 'update.gz')
    else:
      cached_update_file = os.path.join(self.static_dir, 'update.gz')

    # If the new chromiumos image is newer, re-create everything.
    if (os.path.exists(cached_update_file) and
        os.path.getmtime(cached_update_file) >= os.path.getmtime(bin_path)):
      web.debug('Using cached update image at %s instead of %s' %
                (cached_update_file, bin_path))
    else:
      # Unpack zip file if we are serving from a directory.
      if self.serve_only and not self.UnpackZip(image_path, image_file):
        web.debug('unzip image.zip failed.')
        return False

      update_file = os.path.join(image_path, 'update.gz')
      web.debug('Generating update image %s' % update_file)
      mkupdate_command = (
          '%s/cros_generate_update_payload --image=%s --output=%s '
          '--patch_kernel' % (self.scripts_dir, bin_path, update_file))
      if os.system(mkupdate_command) != 0:
        web.debug('Failed to create update image')
        return False

      # Unpack to get stateful partition.
      if not self.UnpackStatefulPartition(image_path, image_file,
                                          stateful_file):
        web.debug('Failed to unpack stateful partition.')
        return False

      mkstatefulupdate_command = 'gzip -f %s' % stateful_file
      if os.system(mkstatefulupdate_command) != 0:
        web.debug('Failed to create stateful update gz')
        return False

      # Add gz suffix
      stateful_file = '%s.gz' % stateful_file

      # Cleanup of image files.
      if not self.serve_only:
        try:
          web.debug('Found a new image to serve, copying it to static')
          shutil.copy(update_file, self.static_dir)
          shutil.copy(stateful_file, self.static_dir)
          os.remove(update_file)
          os.remove(stateful_file)
        except Exception, e:
          web.debug('%s' % e)
          return False
    return True

  def GetSize(self, update_path):
    return os.path.getsize(update_path)

  def GetHash(self, update_path):
    cmd = "cat %s | openssl sha1 -binary | openssl base64 | tr \'\\n\' \' \';" \
        % update_path
    return os.popen(cmd).read().rstrip()

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
          stanza[kind + '_size'] = \
            os.path.getsize(self.static_dir + '/' + stanza[kind + '_image'])
          if validate_checksums:
            factory_checksum = self.GetHash(self.static_dir + '/' +
                                            stanza[kind + '_image'])
            if factory_checksum != stanza[kind + '_checksum']:
              print 'Error: checksum mismatch for %s. Expected "%s" but file ' \
                  'has checksum "%s".' % (stanza[kind + '_image'],
                                          stanza[kind + '_checksum'],
                                          factory_checksum)
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

  def HandleUpdatePing(self, data, label=None):
    web.debug('handle update ping: %s' % data)
    update_dom = minidom.parseString(data)
    root = update_dom.firstChild
    if root.hasAttribute('updaterversion') and \
        not root.getAttribute('updaterversion').startswith(
        self.client_prefix):
      web.debug('Got update from unsupported updater:' + \
          root.getAttribute('updaterversion'))
      return self.GetNoUpdatePayload()
    query = root.getElementsByTagName('o:app')[0]
    client_version = query.getAttribute('version')
    channel = query.getAttribute('track')
    board_id = query.hasAttribute('board') and query.getAttribute('board') \
        or self.GetDefaultBoardID()
    latest_image_path = self.GetLatestImagePath(board_id)
    latest_version = self.GetLatestVersion(latest_image_path)
    hostname = web.ctx.host

    # If this is a factory floor server, return the image here:
    if self.factory_config:
      (filename, checksum, size) = \
          self.GetFactoryImage(board_id, channel)
      if filename is None:
        web.debug('unable to find image for board %s' % board_id)
        return self.GetNoUpdatePayload()
      url = 'http://%s/static/%s' % (hostname, filename)
      web.debug('returning update payload ' + url)
      return self.GetUpdatePayload(checksum, size, url)

    if client_version != 'ForcedUpdate' \
        and not self.CanUpdate(client_version, latest_version):
      web.debug('no update')
      return self.GetNoUpdatePayload()
    if label:
      web.debug('Client requested version %s' % label)
      # Check that matching build exists
      image_path = '%s/%s' % (self.static_dir, label)
      if not os.path.exists(image_path):
        web.debug('%s not found.' % image_path)
        return self.GetNoUpdatePayload()
      # Construct a response
      ok = self.BuildUpdateImage(image_path)
      if ok != True:
        web.debug('Failed to build an update image')
        return self.GetNoUpdatePayload()
      web.debug('serving update: ')
      hash = self.GetHash('%s/%s/update.gz' % (self.static_dir, label))
      size = self.GetSize('%s/%s/update.gz' % (self.static_dir, label))
      # In case we configured images to be hosted elsewhere
      # (e.g. buildbot's httpd), use that. Otherwise, serve it
      # ourselves using web.py's static resource handler.
      if self.static_urlbase:
        urlbase = self.static_urlbase
      else:
        urlbase = 'http://%s/static/archive/' % hostname

      url = '%s/%s/update.gz' % (urlbase, label)
      return self.GetUpdatePayload(hash, size, url)
      web.debug('DONE')
    else:
      web.debug('update found %s ' % latest_version)
      ok = self.BuildUpdateImage(latest_image_path)
      if ok != True:
        web.debug('Failed to build an update image')
        return self.GetNoUpdatePayload()

      hash = self.GetHash('%s/update.gz' % self.static_dir)
      size = self.GetSize('%s/update.gz' % self.static_dir)

      url = 'http://%s/static/update.gz' % hostname
      return self.GetUpdatePayload(hash, size, url)
