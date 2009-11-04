# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import autoupdate
import buildutil
import os
import web
import sys


global updater
updater = None

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
    return updater.HandleUpdatePing(web.data())

  def GET(self):
    web.debug("Value of updater is %s" % updater)

if __name__ == "__main__":

  root_dir = os.path.realpath("%s/../.." % os.path.dirname(os.path.abspath(sys.argv[0])))
  static_dir = os.path.realpath("%s/static" % os.path.dirname(os.path.abspath(sys.argv[0])))
  web.debug("dev root is %s" % root_dir)
  web.debug("Serving images from %s" % static_dir)
  os.system("mkdir -p %s" % static_dir)

  updater = autoupdate.Autoupdate(root_dir=root_dir, static_dir=static_dir)

  urls = ('/', 'index',
          '/update', 'update')
  app = web.application(urls, globals())
  render = web.template.render('templates/')

  app.run()
