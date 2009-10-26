# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from xml.dom import minidom

import os
import web

# TODO(rtc): This is redundant with devserver.py. Move this code to a 
# common location.
app_id = "87efface-864d-49a5-9bb3-4b050a7c227a"
root_dir = "/usr/local/google/home/rtc/chromeos/trunk/src"
scripts_dir = "%s/scripts" % root_dir
app_dir = os.popen("pwd").read().strip()
static_dir = "%s/static" % app_dir

# Basic functionality of handling ChromeOS autoupdate pings 
# and building/serving update images.
# TODO(rtc): Clean this code up and write some tests.

def GetUpdatePayload(hash, size, url, id):
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
  return payload % (id, url, hash, size)

def GetNoUpdatePayload(id):
  payload = """<?xml version="1.0" encoding="UTF-8"?>
    <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
      <app appid="{%s}" status="ok">
        <ping status="ok"/>
        <updatecheck status="noupdate"/>
      </app>
    </gupdate>
  """
  return payload % id

def GetLatestImagePath():
  cmd = "%s/get_latest_image.sh" % scripts_dir
  return os.popen(cmd).read().strip()

def GetLatestVersion(latest_image_path):
  latest_version = latest_image_path.split('/')[-1]
  return latest_version.split('-')[0]

def CanUpdate(client_version, latest_version):
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

def BuildUpdateImage(image_path):
  image_file = "%s/rootfs.image" % image_path
  web.debug("checking image file %s/update.gz" % image_path)
  if not os.path.exists("%s/update.gz" % image_path):
    mkupdate = "%s/mk_memento_images.sh %s" % (scripts_dir, image_file)
    web.debug(mkupdate)
    err = os.system(mkupdate)
    if err != 0:
      web.debug("failed to create update image")
      return False

  web.debug("Found an image, copying it to static")
  err = os.system("cp %s/update.gz %s" % (image_path, static_dir))
  if err != 0:
    web.debug("Unable to move update.gz from %s to %s" % (image_path, static_dir))
    return False
  return True

def GetSize(update_path):
  return os.path.getsize(update_path)

def GetHash(update_path):
  cmd = "cat %s | openssl sha1 -binary | openssl base64 | tr \'\\n\' \' \';" % update_path
  web.debug(cmd)
  return os.popen(cmd).read()

def HandleUpdatePing(data):
  update_dom = minidom.parseString(data)
  root = update_dom.firstChild
  query = root.getElementsByTagName("o:app")[0]
  client_version = query.attributes['version'].value
  latest_image_path = GetLatestImagePath();
  latest_version = GetLatestVersion(latest_image_path);
  if not CanUpdate(client_version, latest_version):
    web.debug("no update")
    return GetNoUpdatePayload(app_id)

  web.debug("update found %s " % latest_version)
  ok = BuildUpdateImage(latest_image_path)
  if ok != True:
    web.debug("Failed to build an update image")
    return GetNoUpdatePayload(app_id)

  hash = GetHash("%s/update.gz" % static_dir)
  size = GetSize("%s/update.gz" % static_dir)
  hostname = web.ctx.host
  url = "http://%s/static/update.gz" % hostname
  return GetUpdatePayload(hash, size, url, app_id)

