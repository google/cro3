# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildutil import BuildObject
from xml.dom import minidom

import os
import shutil
import web

class Autoupdate(BuildObject):
  # Basic functionality of handling ChromeOS autoupdate pings
  # and building/serving update images.
  # TODO(rtc): Clean this code up and write some tests.

  def __init__(self, serve_only=None, test_image=False, urlbase=None,
               *args, **kwargs):
    super(Autoupdate, self).__init__(*args, **kwargs)
    self.serve_only = serve_only
    self.test_image=test_image
    self.static_urlbase = urlbase
    if serve_only:
      # If  we're  serving  out  of  an archived  build  dir  (e.g.  a
      # buildbot), prepare this webserver's magic 'static/' dir with a
      # link to the build archive.
      web.debug('Autoupdate in "serve update images only" mode.')
      if os.path.exists('static/archive'):
        archive_symlink = os.readlink('static/archive')
        if archive_symlink != self.static_dir:
          web.debug('removing stale symlink to %s' % self.static_dir)
          os.unlink('static/archive')
      else:
        os.symlink(self.static_dir, 'static/archive')

  def GetUpdatePayload(self, hash, size, url):
    payload = """<?xml version="1.0" encoding="UTF-8"?>
      <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
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
    return payload % (self.app_id, url, hash, size)

  def GetNoUpdatePayload(self):
    payload = """<?xml version="1.0" encoding="UTF-8"?>
      <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
        <app appid="{%s}" status="ok">
          <ping status="ok"/>
          <updatecheck status="noupdate"/>
        </app>
      </gupdate>
    """
    return payload % self.app_id

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
    client_tokens = client_version.split('.')
    latest_tokens = latest_version.split('.')
    web.debug('client version %s latest version %s' \
        % (client_version, latest_version))
    for i in range(0,4):
      if int(latest_tokens[i]) == int(client_tokens[i]):
        continue
      return int(latest_tokens[i]) > int(client_tokens[i])
    return False

  def UnpackImage(self, image_path, kernel_file, rootfs_file):
    if os.path.exists(rootfs_file) and os.path.exists(kernel_file):
      return True
    if self.test_image:
      image_file = 'chromiumos_test_image.bin'
    else:
      image_file = 'chromiumos_image.bin'
    if self.serve_only:
      os.system('cd %s && unzip -o image.zip' %
                (image_path, image_file))
    os.system('rm -f %s/part_*' % image_path)
    os.system('cd %s && ./unpack_partitions.sh %s' % (image_path, image_file))
    shutil.move(os.path.join(image_path, 'part_2'), kernel_file)
    shutil.move(os.path.join(image_path, 'part_3'), rootfs_file)
    os.system('rm -f %s/part_*' % image_path)
    return True

  def BuildUpdateImage(self, image_path):
    kernel_file = '%s/kernel.image' % image_path
    rootfs_file = '%s/rootfs.image' % image_path

    if not self.UnpackImage(image_path, kernel_file, rootfs_file):
      web.debug('failed to unpack image.')
      return False

    update_file = '%s/update.gz' % image_path
    if (os.path.exists(update_file) and
        os.path.getmtime(update_file) >= os.path.getmtime(rootfs_file)):
      web.debug('Found cached update image %s/update.gz' % image_path)
    else:
      web.debug('generating update image %s' % update_file)
      mkupdate = ('%s/mk_memento_images.sh %s %s' %
                  (self.scripts_dir, kernel_file, rootfs_file))
      web.debug(mkupdate)
      err = os.system(mkupdate)
      if err != 0:
        web.debug('failed to create update image')
        return False
    if not self.serve_only:
      web.debug('Found an image, copying it to static')
      try:
        shutil.copy(update_file, self.static_dir)
      except Exception, e:
        web.debug('Unable to copy %s to %s' % (update_file, self.static_dir))
        return False
    return True

  def GetSize(self, update_path):
    return os.path.getsize(update_path)

  def GetHash(self, update_path):
    cmd = "cat %s | openssl sha1 -binary | openssl base64 | tr \'\\n\' \' \';" \
        % update_path
    web.debug(cmd)
    return os.popen(cmd).read()


  def HandleUpdatePing(self, data, label=None):
    update_dom = minidom.parseString(data)
    root = update_dom.firstChild
    query = root.getElementsByTagName('o:app')[0]
    client_version = query.getAttribute('version')
    board_id = query.hasAttribute('board') and query.getAttribute('board') \
        or 'x86-generic'
    latest_image_path = self.GetLatestImagePath(board_id)
    latest_version = self.GetLatestVersion(latest_image_path)
    if client_version != 'ForcedUpdate' \
        and not self.CanUpdate(client_version, latest_version):
      web.debug('no update')
      return self.GetNoUpdatePayload()
    hostname = web.ctx.host
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
      web.debug( 'DONE')
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
