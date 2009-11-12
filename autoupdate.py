# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from buildutil import BuildObject
from xml.dom import minidom

import os
import web

class Autoupdate(BuildObject):

  # Basic functionality of handling ChromeOS autoupdate pings 
  # and building/serving update images.
  # TODO(rtc): Clean this code up and write some tests.

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

  def GetLatestImagePath(self):
    cmd = "%s/get_latest_image.sh" % self.scripts_dir
    return os.popen(cmd).read().strip()

  def GetLatestVersion(self, latest_image_path):
    latest_version = latest_image_path.split('/')[-1]
    return latest_version.split('-')[0]

  def CanUpdate(self, client_version, latest_version):
    """
      Returns true iff the latest_version is greater than the client_version.
    """
    client_tokens = client_version.split('.')
    latest_tokens = latest_version.split('.')
    web.debug("client version %s latest version %s" % (client_version, latest_version))
    for i in range(0,4):
      if int(latest_tokens[i]) == int(client_tokens[i]):
        continue
      return int(latest_tokens[i]) > int(client_tokens[i])
    return False

  def BuildUpdateImage(self, image_path):
    image_file = "%s/rootfs.image" % image_path
    web.debug("checking image file %s/update.gz" % image_path)
    if not os.path.exists("%s/update.gz" % image_path):
      mkupdate = "%s/mk_memento_images.sh %s" % (self.scripts_dir, image_file)
      web.debug(mkupdate)
      err = os.system(mkupdate)
      if err != 0:
        web.debug("failed to create update image")
        return False

    web.debug("Found an image, copying it to static")
    err = os.system("cp %s/update.gz %s" % (image_path, self.static_dir))
    if err != 0:
      web.debug("Unable to move update.gz from %s to %s" % (image_path, self.static_dir))
      return False
    return True

  def GetSize(self, update_path):
    return os.path.getsize(update_path)

  def GetHash(self, update_path):
    cmd = "cat %s | openssl sha1 -binary | openssl base64 | tr \'\\n\' \' \';" % update_path
    web.debug(cmd)
    return os.popen(cmd).read()

  def HandleUpdatePing(self, data):
    update_dom = minidom.parseString(data)
    root = update_dom.firstChild
    query = root.getElementsByTagName("o:app")[0]
    client_version = query.attributes['version'].value
    latest_image_path = self.GetLatestImagePath();
    latest_version = self.GetLatestVersion(latest_image_path);
    if not self.CanUpdate(client_version, latest_version):
      web.debug("no update")
      return self.GetNoUpdatePayload()

    web.debug("update found %s " % latest_version)
    ok = self.BuildUpdateImage(latest_image_path)
    if ok != True:
      web.debug("Failed to build an update image")
      return self.GetNoUpdatePayload()

    hash = self.GetHash("%s/update.gz" % self.static_dir)
    size = self.GetSize("%s/update.gz" % self.static_dir)
    hostname = web.ctx.host
    url = "http://%s/static/update.gz" % hostname
    return self.GetUpdatePayload(hash, size, url)

