# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import autoupdate
import buildutil
import os
import web

app_id = "87efface-864d-49a5-9bb3-4b050a7c227a"
root_dir = "/usr/local/google/home/rtc/chromeos/trunk/src"
scripts_dir = "%s/scripts" % root_dir
app_dir = os.popen("pwd").read().strip()
static_dir = "%s/static" % app_dir
web.debug("Serving images from %s/static" % app_dir)

urls = ('/', 'index',
        '/update', 'update')

app = web.application(urls, globals())
render = web.template.render('templates/')


class index:
  def GET(self):
    pkgs = buildutil.GetPackages()
    return render.index(pkgs)

class update:
  """
    Processes updates from the client machine. If an update is found, the url 
    references a static link that can be served automagically from web.py.
  """
  def POST(self):
    return autoupdate.HandleUpdatePing(web.data())

if __name__ == "__main__": 
  web.debug("Setting up the static repo")
  os.system("mkdir -p %s" % static_dir)
  app.run()

