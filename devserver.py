# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import autoupdate
import buildutil
import os
import web
import sys

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
  static_dir = os.path.realpath("%s/static" % os.path.dirname(os.path.abspath(sys.argv[0])))
  web.debug("Serving images from %s" % static_dir)
  os.system("mkdir -p %s" % static_dir)
  app.run()
