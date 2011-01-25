#!/usr/bin/python

# Copyright (c) 2009-2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A CherryPy-based webserver to host images and build packages."""

import cherrypy
import optparse
import os
import subprocess
import sys

import autoupdate
import builder

CACHED_ENTRIES = 12

# Sets up global to share between classes.
global updater
updater = None

def _GetConfig(options):
  """Returns the configuration for the devserver."""
  base_config = { 'global':
                  { 'server.log_request_headers': True,
                    'server.protocol_version': 'HTTP/1.1',
                    'server.socket_host': '0.0.0.0',
                    'server.socket_port': int(options.port),
                    'server.socket_timeout': 6000,
                    'response.timeout': 6000,
                    'tools.staticdir.root': os.getcwd(),
                  },
                  '/build':
                  {
                    'response.timeout': 100000,
                  },
                  '/update':
                  {
                    # Gets rid of cherrypy parsing post file for args.
                    'request.process_request_body': False,
                    'response.timeout': 10000,
                  },
                  # Sets up the static dir for file hosting.
                  '/static':
                  { 'tools.staticdir.dir': 'static',
                    'tools.staticdir.on': True,
                    'response.timeout': 10000,
                  },
                }
  if options.production:
    base_config['global']['server.environment'] = 'production'

  return base_config


def _PrepareToServeUpdatesOnly(image_dir):
  """Sets up symlink to image_dir for serving purposes."""
  assert os.path.exists(image_dir), '%s must exist.' % image_dir
  # If  we're  serving  out  of  an archived  build  dir  (e.g.  a
  # buildbot), prepare this webserver's magic 'static/' dir with a
  # link to the build archive.
  cherrypy.log('Preparing autoupdate for "serve updates only" mode.',
               'DEVSERVER')
  if os.path.exists('static/archive'):
    if image_dir != os.readlink('static/archive'):
      cherrypy.log('removing stale symlink to %s' % image_dir, 'DEVSERVER')
      os.unlink('static/archive')
      os.symlink(image_dir, 'static/archive')
  else:
    os.symlink(image_dir, 'static/archive')
  cherrypy.log('archive dir: %s ready to be used to serve images.' % image_dir,
               'DEVSERVER')


class DevServerRoot(object):
  """The Root Class for the Dev Server.

  CherryPy works as follows:
    For each method in this class, cherrpy interprets root/path
    as a call to an instance of DevServerRoot->method_name.  For example,
    a call to http://myhost/build will call build.  CherryPy automatically
    parses http args and places them as keyword arguments in each method.
    For paths http://myhost/update/dir1/dir2, you can use *args so that
    cherrypy uses the update method and puts the extra paths in args.
  """

  def __init__(self):
    self._builder = builder.Builder()

  def build(self, board, pkg, **kwargs):
    """Builds the package specified."""
    return self._builder.Build(board, pkg, kwargs)

  def index(self):
    return 'Welcome to the Dev Server!'

  def update(self, *args):
    label = '/'.join(args)
    body_length = int(cherrypy.request.headers['Content-Length'])
    data = cherrypy.request.rfile.read(body_length)
    return updater.HandleUpdatePing(data, label)

  # Expose actual methods.  Necessary to actually have these callable.
  build.exposed = True
  update.exposed = True
  index.exposed = True


if __name__ == '__main__':
  usage = 'usage: %prog [options]'
  parser = optparse.OptionParser(usage)
  parser.add_option('--archive_dir', dest='archive_dir',
                    help='serve archived builds only.')
  parser.add_option('--board', dest='board',
                    help='When pre-generating update, board for latest image.')
  parser.add_option('--clear_cache', action='store_true', default=False,
                    help='Clear out all cached udpates and exit')
  parser.add_option('--client_prefix', dest='client_prefix',
                    help='Required prefix for client software version.',
                    default='MementoSoftwareUpdate')
  parser.add_option('--exit', action='store_true', default=False,
                    help='Don\'t start the server (still pregenerate or clear'
                         'cache).')
  parser.add_option('--factory_config', dest='factory_config',
                    help='Config file for serving images from factory floor.')
  parser.add_option('--for_vm', dest='vm', default=False, action='store_true',
                    help='Update is for a vm image.')
  parser.add_option('--image', dest='image',
                    help='Force update using this image.')
  parser.add_option('-p', '--pregenerate_update', action='store_true',
                    default=False, help='Pre-generate update payload.')
  parser.add_option('--payload', dest='payload',
                    help='Use update payload from specified directory.')
  parser.add_option('--port', default=8080,
                    help='Port for the dev server to use.')
  parser.add_option('--production', action='store_true', default=False,
                    help='Have the devserver use production values.')
  parser.add_option('--proxy_port', default=None,
                    help='Port to have the client connect to (testing support)')
  parser.add_option('--src_image', default='',
                    help='Image on remote machine for generating delta update.')
  parser.add_option('-t', action='store_true', dest='test_image')
  parser.add_option('-u', '--urlbase', dest='urlbase',
                    help='base URL, other than devserver, for update images.')
  parser.add_option('--validate_factory_config', action="store_true",
                    dest='validate_factory_config',
                    help='Validate factory config file, then exit.')
  parser.set_usage(parser.format_help())
  (options, _) = parser.parse_args()

  devserver_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
  root_dir = os.path.realpath('%s/../..' % devserver_dir)
  serve_only = False

  if options.archive_dir:
    static_dir = os.path.realpath(options.archive_dir)
    _PrepareToServeUpdatesOnly(static_dir)
    serve_only = True
  else:
    static_dir = os.path.realpath('%s/static' % devserver_dir)
    os.system('mkdir -p %s' % static_dir)

  cache_dir = os.path.join(static_dir, 'cache')
  cherrypy.log('Using cache directory %s' % cache_dir, 'DEVSERVER')

  if options.clear_cache:
    # Clear the cache and exit on error
    if os.system('sudo rm -rf %s' % cache_dir) != 0:
      cherrypy.log('Failed to clear the cache with %s' % cmd,
                   'DEVSERVER')
      sys.exit(1)

  if os.path.exists(cache_dir):
    # Clear all but the last N cached updates
    cmd = ('cd %s; ls -tr | head --lines=-%d | xargs rm -rf' %
           (cache_dir, CACHED_ENTRIES))
    if os.system(cmd) != 0:
      cherrypy.log('Failed to clean up old delta cache files with %s' % cmd,
                   'DEVSERVER')
      sys.exit(1)

  cherrypy.log('Source root is %s' % root_dir, 'DEVSERVER')
  cherrypy.log('Serving from %s' % static_dir, 'DEVSERVER')

  updater = autoupdate.Autoupdate(
      root_dir=root_dir,
      static_dir=static_dir,
      serve_only=serve_only,
      urlbase=options.urlbase,
      test_image=options.test_image,
      factory_config_path=options.factory_config,
      client_prefix=options.client_prefix,
      forced_image=options.image,
      forced_payload=options.payload,
      port=options.port,
      proxy_port=options.proxy_port,
      src_image=options.src_image,
      vm=options.vm,
      board=options.board,
      copy_to_static_root=not options.exit)

  # Sanity-check for use of validate_factory_config.
  if not options.factory_config and options.validate_factory_config:
    parser.error('You need a factory_config to validate.')

  if options.factory_config:
    updater.ImportFactoryConfigFile(options.factory_config,
                                     options.validate_factory_config)
    # We don't run the dev server with this option.
    if options.validate_factory_config:
      sys.exit(0)
  elif options.pregenerate_update:
    if not updater.PreGenerateUpdate():
      sys.exit(1)

  # If the command line requested after setup, it's time to do it.
  if not options.exit:
    cherrypy.quickstart(DevServerRoot(), config=_GetConfig(options))
