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

global buildbot
buildbot = None

class index:
  def GET(self):
    pkgs = buildbot.GetPackages()
    return render.index(pkgs)

class update:
  """
    Processes updates from the client machine. If an update is found, the url 
    references a static link that can be served automagically from web.py.
  """
  def POST(self):
    return updater.HandleUpdatePing(web.data())

class webbuild:
  """
    builds the package specified by the pkg parameter. Then redirects to index
  """
  def GET(self):
    input = web.input()
    web.debug("called %s " % input.pkg)
    output = buildbot.BuildPackage(input.pkg)
    web.debug("copied %s to static" % output)
    raise web.seeother('/')

class build:
  """
    builds the package specified by the pkg parameter and returns the name
    of the output file.
  """
  def GET(self):
    input = web.input()
    web.debug("called %s " % input.pkg)
    return buildbot.BuildPackage(input.pkg)

if __name__ == "__main__":

  root_dir = os.path.realpath("%s/../.." % os.path.dirname(os.path.abspath(sys.argv[0])))
  static_dir = os.path.realpath("%s/static" % os.path.dirname(os.path.abspath(sys.argv[0])))
  web.debug("dev root is %s" % root_dir)
  web.debug("Serving images from %s" % static_dir)
  os.system("mkdir -p %s" % static_dir)

  updater = autoupdate.Autoupdate(root_dir=root_dir, static_dir=static_dir)
  buildbot = buildutil.BuildUtil(root_dir=root_dir, static_dir=static_dir)

  urls = ('/', 'index',
          '/update', 'update',
          '/webbuild', 'webbuild',
          '/build', 'build')

  app = web.application(urls, globals())
  render = web.template.render('templates/')

  app.run()
