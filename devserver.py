# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import autoupdate
import buildutil
import optparse
import os
import SimpleHTTPServer
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
  def POST(self, args=None):
    return updater.HandleUpdatePing(web.data(), args)

class build:
  """
    builds the package specified by the pkg parameter and returns the name
    of the output file.
  """
  def POST(self):
    input = web.input()
    web.debug('emerging %s ' % input.pkg)
    emerge_command = 'emerge-%s %s' % (input.board, input.pkg)
    err = os.system(emerge_command)
    if err != 0:
      raise Exception('failed to execute %s' % emerge_command)

if __name__ == '__main__':
  usage = 'usage: %prog [options]'
  parser = optparse.OptionParser(usage)
  parser.add_option('-a', '--archive_dir', dest='archive_dir',
                    help='serve archived builds only.')
  parser.add_option("-t", action="store_true", dest="test_image")
  options, args = parser.parse_args()
  # clean up the args, due to httpserver's hardcoded use of sys.argv
  if options.archive_dir:
    sys.argv.remove('-a')
    sys.argv.remove(options.archive_dir)
  if options.test_image:
    sys.argv.remove('-t')


  root_dir = os.path.realpath('%s/../..' %
                              os.path.dirname(os.path.abspath(sys.argv[0])))
  if options.archive_dir:
    static_dir = os.path.realpath(options.archive_dir)
    assert os.path.exists(static_dir), '%s must exist.' % options.archive_dir
    web.debug('using archive dir: %s' % static_dir)
  else:
    static_dir = os.path.realpath('%s/static' %
        os.path.dirname(os.path.abspath(sys.argv[0])))
    web.debug('dev root is %s' % root_dir)
    os.system('mkdir -p %s' % static_dir)
  web.debug('Serving images from %s' % static_dir)

  updater = autoupdate.Autoupdate(root_dir=root_dir,
                                  static_dir=static_dir,
                                  serve_only=options.archive_dir,
                                  test_image=options.test_image)
  urls = ('/', 'index',
          '/update', 'update',
          '/update/(.+)', 'update',
          '/webbuild', 'webbuild',
          '/build', 'build')

  app = web.application(urls, globals(), autoreload=True)
  render = web.template.render('templates/')
  app.run()
