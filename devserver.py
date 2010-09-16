# Copyright (c) 2009-2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import optparse
import os
import sys
import web

import autoupdate
import buildutil

# Sets up global to share between classes.
global updater
updater = None


class index:
  def GET(self):
    return render.index(None)


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
    eclean_command = 'eclean-%s -d packages' % input.board
    err = os.system(eclean_command)
    if err != 0:
      raise Exception('failed to execute %s' % emerge_command)


def OverrideWSGIServer(server_address, wsgi_app):
  """Creates a CherryPyWSGIServer instance.

  Overrides web.py's WSGIServer routine (web.httpserver.WSGIServer) to
  increase the accepted connection socket timeout from the default 10
  seconds to 10 minutes. The extra time is necessary to serve delta
  updates as well as update requests from a low priority update_engine
  process running on a heavily loaded Chrome OS device.
  """
  web.debug('using local OverrideWSGIServer routine')
  from web.wsgiserver import CherryPyWSGIServer
  return CherryPyWSGIServer(server_address, wsgi_app, server_name="localhost",
                            timeout=600)

def _PrepareToServeUpdatesOnly(image_dir):
  """Sets up symlink to image_dir for serving purposes."""
  assert os.path.exists(image_dir), '%s must exist.' % image_dir
  # If  we're  serving  out  of  an archived  build  dir  (e.g.  a
  # buildbot), prepare this webserver's magic 'static/' dir with a
  # link to the build archive.
  web.debug('Preparing autoupdate for "serve updates only" mode.')
  if os.path.exists('static/archive'):
    if image_dir != os.readlink('static/archive'):
      web.debug('removing stale symlink to %s' % image_dir)
      os.unlink('static/archive')
      os.symlink(image_dir, 'static/archive')
  else:
    os.symlink(image_dir, 'static/archive')
  web.debug('archive dir: %s ready to be used to serve images.' % image_dir)


if __name__ == '__main__':
  usage = 'usage: %prog [options]'
  parser = optparse.OptionParser(usage)
  parser.add_option('--archive_dir', dest='archive_dir',
                    help='serve archived builds only.')
  parser.add_option('--client_prefix', dest='client_prefix',
                    help='Required prefix for client software version.',
                    default='MementoSoftwareUpdate')
  parser.add_option('--factory_config', dest='factory_config',
                    help='Config file for serving images from factory floor.')
  parser.add_option('--image', dest='image',
                    help='Force update using this image.')
  parser.add_option('-t', action='store_true', dest='test_image')
  parser.add_option('-u', '--urlbase', dest='urlbase',
                    help='base URL, other than devserver, for update images.')
  parser.add_option('--validate_factory_config', action="store_true",
                    dest='validate_factory_config',
                    help='Validate factory config file, then exit.')
  # Clean up the args, due to httpserver's hardcoded use of sys.argv.
  options, sys.argv = parser.parse_args(sys.argv)

  root_dir = os.path.realpath('%s/../..' %
                              os.path.dirname(os.path.abspath(sys.argv[0])))

  serve_only = False

  if options.archive_dir:
    static_dir = os.path.realpath(options.archive_dir)
    _PrepareToServeUpdatesOnly(static_dir)
    serve_only = True
  else:
    static_dir = os.path.realpath('%s/static' %
        os.path.dirname(os.path.abspath(sys.argv[0])))
    web.debug('dev root is %s' % root_dir)
    os.system('mkdir -p %s' % static_dir)

  web.debug('Serving from %s' % static_dir)

  updater = autoupdate.Autoupdate(
      root_dir=root_dir,
      static_dir=static_dir,
      serve_only=serve_only,
      urlbase=options.urlbase,
      test_image=options.test_image,
      factory_config_path=options.factory_config,
      client_prefix=options.client_prefix,
      forced_image=options.image)

  if options.factory_config:
     updater.ImportFactoryConfigFile(factory_config_path,
                                     validate_factory_config)

  if not options.validate_factory_config:
    # We do not need to run the dev server for validating the factory config.
    # TODO(nsanders): Write unit test to validate.
    urls = ('/', 'index',
            '/update', 'update',
            '/update/(.+)', 'update',
            '/build', 'build')

    # Overrides the default WSGIServer routine -- see OverrideWSGIServer.
    web.httpserver.WSGIServer = OverrideWSGIServer
    app = web.application(urls, globals(), autoreload=True)
    render = web.template.render('templates/')
    app.run()
