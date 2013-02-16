#!/usr/bin/python

# Copyright (c) 2009-2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A CherryPy-based webserver to host images and build packages."""

import cherrypy
import json
import optparse
import os
import re
import shutil
import socket
import sys
import subprocess
import tempfile
import types

import autoupdate
import common_util
import downloader
import log_util


# Module-local log function.
def _Log(message, *args):
  return log_util.LogWithTag('DEVSERVER', message, *args)


CACHED_ENTRIES = 12

TELEMETRY_FOLDER = 'telemetry_src'
TELEMETRY_DEPS = ['dep-telemetry_dep.tar.bz2',
                  'dep-page_cycler_dep.tar.bz2',
                  'dep-chrome_test.tar.bz2']

# Sets up global to share between classes.
updater = None


class DevServerError(Exception):
  """Exception class used by this module."""
  pass


def _LeadingWhiteSpaceCount(string):
  """Count the amount of leading whitespace in a string.

  Args:
    string: The string to count leading whitespace in.
  Returns:
    number of white space chars before characters start.
  """
  matched = re.match('^\s+', string)
  if matched:
    return len(matched.group())

  return 0


def _PrintDocStringAsHTML(func):
  """Make a functions docstring somewhat HTML style.

  Args:
    func: The function to return the docstring from.
  Returns:
    A string that is somewhat formated for a web browser.
  """
  # TODO(scottz): Make this parse Args/Returns in a prettier way.
  # Arguments could be bolded and indented etc.
  html_doc = []
  for line in func.__doc__.splitlines():
    leading_space = _LeadingWhiteSpaceCount(line)
    if leading_space > 0:
      line = '&nbsp;' * leading_space + line

    html_doc.append('<BR>%s' % line)

  return '\n'.join(html_doc)


def _GetConfig(options):
  """Returns the configuration for the devserver."""

  # On a system with IPv6 not compiled into the kernel,
  # AF_INET6 sockets will return a socket.error exception.
  # On such systems, fall-back to IPv4.
  socket_host = '::'
  try:
    socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
  except socket.error:
    socket_host = '0.0.0.0'

  base_config = { 'global':
                  { 'server.log_request_headers': True,
                    'server.protocol_version': 'HTTP/1.1',
                    'server.socket_host': socket_host,
                    'server.socket_port': int(options.port),
                    'response.timeout': 6000,
                    'request.show_tracebacks': True,
                    'server.socket_timeout': 60,
                    'tools.staticdir.root':
                      os.path.dirname(os.path.abspath(sys.argv[0])),
                  },
                  '/api':
                  {
                    # Gets rid of cherrypy parsing post file for args.
                    'request.process_request_body': False,
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
    base_config['global'].update({'server.thread_pool': 75})

  return base_config


def _PrepareToServeUpdatesOnly(image_dir, static_dir):
  """Sets up symlink to image_dir for serving purposes."""
  assert os.path.exists(image_dir), '%s must exist.' % image_dir
  # If  we're  serving  out  of  an archived  build  dir  (e.g.  a
  # buildbot), prepare this webserver's magic 'static/' dir with a
  # link to the build archive.
  _Log('Preparing autoupdate for "serve updates only" mode.')
  if os.path.lexists('%s/archive' % static_dir):
    if image_dir != os.readlink('%s/archive' % static_dir):
      _Log('removing stale symlink to %s' % image_dir)
      os.unlink('%s/archive' % static_dir)
      os.symlink(image_dir, '%s/archive' % static_dir)

  else:
    os.symlink(image_dir, '%s/archive' % static_dir)

  _Log('archive dir: %s ready to be used to serve images.' % image_dir)


def _GetRecursiveMemberObject(root, member_list):
  """Returns an object corresponding to a nested member list.

  Args:
    root: the root object to search
    member_list: list of nested members to search
  Returns:
    An object corresponding to the member name list; None otherwise.
  """
  for member in member_list:
    next_root = root.__class__.__dict__.get(member)
    if not next_root:
      return None
    root = next_root
  return root


def _IsExposed(name):
  """Returns True iff |name| has an `exposed' attribute and it is set."""
  return hasattr(name, 'exposed') and name.exposed


def _GetExposedMethod(root, nested_member, ignored=None):
  """Returns a CherryPy-exposed method, if such exists.

  Args:
    root: the root object for searching
    nested_member: a slash-joined path to the nested member
    ignored: method paths to be ignored
  Returns:
    A function object corresponding to the path defined by |member_list| from
    the |root| object, if the function is exposed and not ignored; None
    otherwise.
  """
  method = (not (ignored and nested_member in ignored) and
            _GetRecursiveMemberObject(root, nested_member.split('/')))
  if (method and type(method) == types.FunctionType and _IsExposed(method)):
    return method


def _FindExposedMethods(root, prefix, unlisted=None):
  """Finds exposed CherryPy methods.

  Args:
    root: the root object for searching
    prefix: slash-joined chain of members leading to current object
    unlisted: URLs to be excluded regardless of their exposed status
  Returns:
    List of exposed URLs that are not unlisted.
  """
  method_list = []
  for member in sorted(root.__class__.__dict__.keys()):
    prefixed_member = prefix + '/' + member if prefix else member
    if unlisted and prefixed_member in unlisted:
      continue
    member_obj = root.__class__.__dict__[member]
    if _IsExposed(member_obj):
      if type(member_obj) == types.FunctionType:
        method_list.append(prefixed_member)
      else:
        method_list += _FindExposedMethods(
            member_obj, prefixed_member, unlisted)
  return method_list


class ApiRoot(object):
  """RESTful API for Dev Server information."""
  exposed = True

  @cherrypy.expose
  def hostinfo(self, ip):
    """Returns a JSON dictionary containing information about the given ip.

    Args:
      ip: address of host whose info is requested
    Returns:
      A JSON dictionary containing all or some of the following fields:
        last_event_type (int):        last update event type received
        last_event_status (int):      last update event status received
        last_known_version (string):  last known version reported in update ping
        forced_update_label (string): update label to force next update ping to
                                      use, set by setnextupdate
      See the OmahaEvent class in update_engine/omaha_request_action.h for
      event type and status code definitions. If the ip does not exist an empty
      string is returned.

    Example URL:
      http://myhost/api/hostinfo?ip=192.168.1.5
    """
    return updater.HandleHostInfoPing(ip)

  @cherrypy.expose
  def hostlog(self, ip):
    """Returns a JSON object containing a log of host event.

    Args:
      ip: address of host whose event log is requested, or `all'
    Returns:
      A JSON encoded list (log) of dictionaries (events), each of which
      containing a `timestamp' and other event fields, as described under
      /api/hostinfo.

    Example URL:
      http://myhost/api/hostlog?ip=192.168.1.5
    """
    return updater.HandleHostLogPing(ip)

  @cherrypy.expose
  def setnextupdate(self, ip):
    """Allows the response to the next update ping from a host to be set.

    Takes the IP of the host and an update label as normally provided to the
    /update command.
    """
    body_length = int(cherrypy.request.headers['Content-Length'])
    label = cherrypy.request.rfile.read(body_length)

    if label:
      label = label.strip()
      if label:
        return updater.HandleSetUpdatePing(ip, label)
    raise cherrypy.HTTPError(400, 'No label provided.')


  @cherrypy.expose
  def fileinfo(self, *path_args):
    """Returns information about a given staged file.

    Args:
      path_args: path to the file inside the server's static staging directory
    Returns:
      A JSON encoded dictionary with information about the said file, which may
      contain the following keys/values:
        size (int):      the file size in bytes
        sha1 (string):   a base64 encoded SHA1 hash
        sha256 (string): a base64 encoded SHA256 hash

    Example URL:
      http://myhost/api/fileinfo/some/path/to/file
    """
    file_path = os.path.join(updater.static_dir, *path_args)
    if not os.path.exists(file_path):
      raise DevServerError('file not found: %s' % file_path)
    try:
      file_size = os.path.getsize(file_path)
      file_sha1 = common_util.GetFileSha1(file_path)
      file_sha256 = common_util.GetFileSha256(file_path)
    except os.error, e:
      raise DevServerError('failed to get info for file %s: %s' %
                           (file_path, e))

    is_delta = autoupdate.Autoupdate.IsDeltaFormatFile(file_path)

    return json.dumps({
        autoupdate.Autoupdate.SIZE_ATTR: file_size,
        autoupdate.Autoupdate.SHA1_ATTR: file_sha1,
        autoupdate.Autoupdate.SHA256_ATTR: file_sha256,
        autoupdate.Autoupdate.ISDELTA_ATTR: is_delta
    })


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
  # Method names that should not be listed on the index page.
  _UNLISTED_METHODS = ['index', 'doc']

  api = ApiRoot()

  def __init__(self):
    self._builder = None
    self._telemetry_lock_dict = common_util.LockDict()

  @cherrypy.expose
  def build(self, board, pkg, **kwargs):
    """Builds the package specified."""
    import builder
    if self._builder is None:
      self._builder = builder.Builder()
    return self._builder.Build(board, pkg, kwargs)

  @staticmethod
  def _canonicalize_archive_url(archive_url):
    """Canonicalizes archive_url strings.

    Raises:
      DevserverError: if archive_url is not set.
    """
    if archive_url:
      if not archive_url.startswith('gs://'):
        raise DevServerError("Archive URL isn't from Google Storage.")

      return archive_url.rstrip('/')
    else:
      raise DevServerError("Must specify an archive_url in the request")

  @cherrypy.expose
  def download(self, **kwargs):
    """Downloads and archives full/delta payloads from Google Storage.

    THIS METHOD IS DEPRECATED: use stage(..., artifacts=...) instead.
    This methods downloads artifacts. It may download artifacts in the
    background in which case a caller should call wait_for_status to get
    the status of the background artifact downloads. They should use the same
    args passed to download.

    Args:
      archive_url: Google Storage URL for the build.

    Example URL:
      http://myhost/download?archive_url=gs://chromeos-image-archive/
      x86-generic/R17-1208.0.0-a1-b338
    """
    return self.stage(archive_url=kwargs.get('archive_url'),
                      artifacts='full_payload,test_suites,stateful')

  @cherrypy.expose
  def stage(self, **kwargs):
    """Downloads and caches the artifacts from Google Storage URL.

    Downloads and caches the artifacts Google Storage URL. Returns once these
    have been downloaded on the devserver. A call to this will attempt to cache
    non-specified artifacts in the background for the given from the given URL
    following the principle of spatial locality. Spatial locality of different
    artifacts is explicitly defined in the build_artifact module.

    These artifacts will then be available from the static/ sub-directory of
    the devserver.

    Args:
      archive_url: Google Storage URL for the build.
      artifacts: Comma separated list of artifacts to download.

    Example:
      To download the autotest and test suites tarballs:
        http://devserver_url:<port>/stage?archive_url=gs://your_url/path&
            artifacts=autotest,test_suites
      To download the full update payload:
        http://devserver_url:<port>/stage?archive_url=gs://your_url/path&
            artifacts=full_payload

      For both these examples, one could find these artifacts at:
        http://devserver_url:<port>/static/archive/<relative_path>*

      Note for this example, relative path is the archive_url stripped of its
      basename i.e. path/ in the examples above. Specific example:

      gs://chromeos-image-archive/x86-mario-release/R26-3920.0.0

      Will get staged to:

      http://devserver_url:<port>/static/archive/x86-mario-release/R26-3920.0.0
    """
    archive_url = self._canonicalize_archive_url(kwargs.get('archive_url'))
    artifacts = kwargs.get('artifacts', '')
    if not artifacts:
      raise DevServerError('No artifacts specified.')

    downloader.Downloader(updater.static_dir, archive_url).Download(
        artifacts.split(','))
    return 'Success'

  @cherrypy.expose
  def setup_telemetry(self, **kwargs):
    """Extracts and sets up telemetry

    This method goes through the telemetry deps packages, and stages them on
    the devserver to be used by the drones and the telemetry tests.

    Args:
      archive_url: Google Storage URL for the build.

    Returns:
      Path to the source folder for the telemetry codebase once it is staged.
    """
    archive_url = kwargs.get('archive_url')
    self.stage(archive_url=archive_url, artifacts='autotest')

    build = '/'.join(downloader.Downloader.ParseUrl(archive_url))
    build_path = os.path.join(updater.static_dir, build)
    deps_path = os.path.join(build_path, 'autotest/packages')
    telemetry_path = os.path.join(build_path, TELEMETRY_FOLDER)
    src_folder = os.path.join(telemetry_path, 'src')

    with self._telemetry_lock_dict.lock(telemetry_path):
      if os.path.exists(src_folder):
        # Telemetry is already fully stage return
        return src_folder

      common_util.MkDirP(telemetry_path)

      # Copy over the required deps tar balls to the telemetry directory.
      for dep in TELEMETRY_DEPS:
        dep_path = os.path.join(deps_path, dep)
        try:
          common_util.ExtractTarball(dep_path, telemetry_path)
        except common_util.CommonUtilError as e:
          shutil.rmtree(telemetry_path)
          raise DevServerError(str(e))

      # By default all the tarballs extract to test_src but some parts of
      # the telemetry code specifically hardcoded to exist inside of 'src'.
      test_src = os.path.join(telemetry_path, 'test_src')
      try:
        shutil.move(test_src, src_folder)
      except shutil.Error:
        # This can occur if src_folder already exists. Remove and retry move.
        shutil.rmtree(src_folder)
        raise DevServerError('Failure in telemetry setup for build %s. Appears'
                             ' that the test_src to src move failed.' % build)

      return src_folder

  @cherrypy.expose
  def wait_for_status(self, **kwargs):
    """Waits for background artifacts to be downloaded from Google Storage.

    THIS METHOD IS DEPRECATED: use stage(..., artifacts=...) instead.
    Args:
      archive_url: Google Storage URL for the build.

    Example URL:
      http://myhost/wait_for_status?archive_url=gs://chromeos-image-archive/
      x86-generic/R17-1208.0.0-a1-b338
    """
    return self.stage(archive_url=kwargs.get('archive_url'),
                      artifacts='full_payload,test_suites,autotest,stateful')

  @cherrypy.expose
  def stage_debug(self, **kwargs):
    """Downloads and stages debug symbol payloads from Google Storage.

    THIS METHOD IS DEPRECATED: use stage(..., artifacts=...) instead.
    This methods downloads the debug symbol build artifact
    synchronously, and then stages it for use by symbolicate_dump.

    Args:
      archive_url: Google Storage URL for the build.

    Example URL:
      http://myhost/stage_debug?archive_url=gs://chromeos-image-archive/
      x86-generic/R17-1208.0.0-a1-b338
    """
    return self.stage(archive_url=kwargs.get('archive_url'),
                      artifacts='symbols')

  @cherrypy.expose
  def symbolicate_dump(self, minidump, **kwargs):
    """Symbolicates a minidump using pre-downloaded symbols, returns it.

    Callers will need to POST to this URL with a body of MIME-type
    "multipart/form-data".
    The body should include a single argument, 'minidump', containing the
    binary-formatted minidump to symbolicate.

    Args:
      archive_url: Google Storage URL for the build.
      minidump: The binary minidump file to symbolicate.
    """
    # Ensure the symbols have been staged.
    archive_url = self._canonicalize_archive_url(kwargs.get('archive_url'))
    if self.stage(archive_url=archive_url, artifacts='symbols') != 'Success':
      raise DevServerError('Failed to stage symbols for %s' % archive_url)

    to_return = ''
    with tempfile.NamedTemporaryFile() as local:
      while True:
        data = minidump.file.read(8192)
        if not data:
          break
        local.write(data)

      local.flush()

      symbols_directory = os.path.join(downloader.Downloader.GetBuildDir(
          updater.static_dir, archive_url), 'debug', 'breakpad')

      stackwalk = subprocess.Popen(
          ['minidump_stackwalk', local.name, symbols_directory],
          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

      to_return, error_text = stackwalk.communicate()
      if stackwalk.returncode != 0:
        raise DevServerError("Can't generate stack trace: %s (rc=%d)" % (
            error_text, stackwalk.returncode))

    return to_return

  @cherrypy.expose
  def latestbuild(self, **params):
    """Return a string representing the latest build for a given target.

    Args:
      target: The build target, typically a combination of the board and the
          type of build e.g. x86-mario-release.
      milestone: The milestone to filter builds on. E.g. R16. Optional, if not
          provided the latest RXX build will be returned.
    Returns:
      A string representation of the latest build if one exists, i.e.
          R19-1993.0.0-a1-b1480.
      An empty string if no latest could be found.
    """
    if not params:
      return _PrintDocStringAsHTML(self.latestbuild)

    if 'target' not in params:
      raise cherrypy.HTTPError('500 Internal Server Error',
                               'Error: target= is required!')
    try:
      return common_util.GetLatestBuildVersion(
          updater.static_dir, params['target'],
          milestone=params.get('milestone'))
    except common_util.CommonUtilError as errmsg:
      raise cherrypy.HTTPError('500 Internal Server Error', str(errmsg))

  @cherrypy.expose
  def controlfiles(self, **params):
    """Return a control file or a list of all known control files.

    Example URL:
      To List all control files:
      http://dev-server/controlfiles?board=x86-alex-release&build=R18-1514.0.0
      To return the contents of a path:
      http://dev-server/controlfiles?board=x86-alex-release&build=R18-1514.0.0&control_path=client/sleeptest/control

    Args:
      build: The build i.e. x86-alex-release/R18-1514.0.0-a1-b1450.
      control_path: If you want the contents of a control file set this
        to the path. E.g. client/site_tests/sleeptest/control
        Optional, if not provided return a list of control files is returned.
    Returns:
      Contents of a control file if control_path is provided.
      A list of control files if no control_path is provided.
    """
    if not params:
      return _PrintDocStringAsHTML(self.controlfiles)

    if 'build' not in params:
      raise cherrypy.HTTPError('500 Internal Server Error',
                               'Error: build= is required!')

    if 'control_path' not in params:
      return common_util.GetControlFileList(
          updater.static_dir, params['build'])
    else:
      return common_util.GetControlFile(
          updater.static_dir, params['build'], params['control_path'])

  @cherrypy.expose
  def stage_images(self, **kwargs):
    """Downloads and stages a Chrome OS image from Google Storage.

    THIS METHOD IS DEPRECATED: use stage(..., artifacts=...) instead.
    This method downloads a zipped archive from a specified GS location, then
    extracts and stages the specified list of images and stages them under
    static/BOARD/BUILD/. Download is synchronous.

    Args:
      archive_url: Google Storage URL for the build.
      image_types: comma-separated list of images to download, may include
                   'test', 'recovery', and 'base'

    Example URL:
      http://myhost/stage_images?archive_url=gs://chromeos-image-archive/
      x86-generic/R17-1208.0.0-a1-b338&image_types=test,base
    """
    image_types = kwargs.get('image_types').split(',')
    image_types_list = [image + '_image' for image in image_types]
    self.stage(archive_url=kwargs.get('archive_url'), artifacts=','.join(
        image_types_list))

  @cherrypy.expose
  def index(self):
    """Presents a welcome message and documentation links."""
    return ('Welcome to the Dev Server!<br>\n'
            '<br>\n'
            'Here are the available methods, click for documentation:<br>\n'
            '<br>\n'
            '%s' %
            '<br>\n'.join(
                [('<a href=doc/%s>%s</a>' % (name, name))
                 for name in _FindExposedMethods(
                     self, '', unlisted=self._UNLISTED_METHODS)]))

  @cherrypy.expose
  def doc(self, *args):
    """Shows the documentation for available methods / URLs.

    Example:
      http://myhost/doc/update
    """
    name = '/'.join(args)
    method = _GetExposedMethod(self, name)
    if not method:
      raise DevServerError("No exposed method named `%s'" % name)
    if not method.__doc__:
      raise DevServerError("No documentation for exposed method `%s'" % name)
    return '<pre>\n%s</pre>' % method.__doc__

  @cherrypy.expose
  def update(self, *args):
    """Handles an update check from a Chrome OS client.

    The HTTP request should contain the standard Omaha-style XML blob. The URL
    line may contain an additional intermediate path to the update payload.

    Example:
      http://myhost/update/optional/path/to/payload
    """
    label = '/'.join(args)
    body_length = int(cherrypy.request.headers.get('Content-Length', 0))
    data = cherrypy.request.rfile.read(body_length)
    return updater.HandleUpdatePing(data, label)


def _CleanCache(cache_dir, wipe):
  """Wipes any excess cached items in the cache_dir.

  Args:
    cache_dir: the directory we are wiping from.
    wipe: If True, wipe all the contents -- not just the excess.
  """
  if wipe:
    # Clear the cache and exit on error.
    cmd = 'rm -rf %s/*' % cache_dir
    if os.system(cmd) != 0:
      _Log('Failed to clear the cache with %s' % cmd)
      sys.exit(1)
  else:
    # Clear all but the last N cached updates
    cmd = ('cd %s; ls -tr | head --lines=-%d | xargs rm -rf' %
           (cache_dir, CACHED_ENTRIES))
    if os.system(cmd) != 0:
      _Log('Failed to clean up old delta cache files with %s' % cmd)
      sys.exit(1)


def main():
  usage = 'usage: %prog [options]'
  parser = optparse.OptionParser(usage=usage)
  parser.add_option('--archive_dir',
                    metavar='PATH',
                    help='Enables serve-only mode. Serves archived builds only')
  parser.add_option('--board',
                    help='when pre-generating update, board for latest image')
  parser.add_option('--clear_cache',
                    action='store_true', default=False,
                    help='clear out all cached updates and exit')
  parser.add_option('--critical_update',
                    action='store_true', default=False,
                    help='present update payload as critical')
  parser.add_option('--data_dir',
                    metavar='PATH',
                    default=os.path.dirname(os.path.abspath(sys.argv[0])),
                    help='writable directory where static lives')
  parser.add_option('--exit',
                    action='store_true',
                    help='do not start server (yet pregenerate/clear cache)')
  parser.add_option('--for_vm',
                    dest='vm', action='store_true',
                    help='update is for a vm image')
  parser.add_option('--host_log',
                    action='store_true', default=False,
                    help='record history of host update events (/api/hostlog)')
  parser.add_option('--image',
                    metavar='FILE',
                    help='Force update using this image. Can only be used when '
                    'not in serve-only mode as it is used to generate a '
                    'payload.')
  parser.add_option('--logfile',
                    metavar='PATH',
                    help='log output to this file instead of stdout')
  parser.add_option('--max_updates',
                    metavar='NUM', default= -1, type='int',
                    help='maximum number of update checks handled positively '
                         '(default: unlimited)')
  parser.add_option('-p', '--pregenerate_update',
                    action='store_true', default=False,
                    help='pre-generate update payload. Can only be used when '
                    'not in serve-only mode as it is used to generate a '
                    'payload.')
  parser.add_option('--payload',
                    metavar='PATH',
                    help='use update payload from specified directory')
  parser.add_option('--port',
                    default=8080, type='int',
                    help='port for the dev server to use (default: 8080)')
  parser.add_option('--private_key',
                    metavar='PATH', default=None,
                    help='path to the private key in pem format')
  parser.add_option('--production',
                    action='store_true', default=False,
                    help='have the devserver use production values')
  parser.add_option('--proxy_port',
                    metavar='PORT', default=None, type='int',
                    help='port to have the client connect to (testing support)')
  parser.add_option('--remote_payload',
                    action='store_true', default=False,
                    help='Payload is being served from a remote machine')
  parser.add_option('--src_image',
                    metavar='PATH', default='',
                    help='source image for generating delta updates from')
  parser.add_option('-t', '--test_image',
                    action='store_true',
                    help='whether or not to use test images')
  parser.add_option('-u', '--urlbase',
                    metavar='URL',
                    help='base URL for update images, other than the devserver')
  (options, _) = parser.parse_args()

  devserver_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
  root_dir = os.path.realpath('%s/../..' % devserver_dir)
  serve_only = False

  static_dir = os.path.realpath('%s/static' % options.data_dir)
  os.system('mkdir -p %s' % static_dir)

  if options.archive_dir:
  # TODO(zbehan) Remove legacy support:
  #  archive_dir is the directory where static/archive will point.
  #  If this is an absolute path, all is fine. If someone calls this
  #  using a relative path, that is relative to src/platform/dev/.
  #  That use case is unmaintainable, but since applications use it
  #  with =./static, instead of a boolean flag, we'll make this relative
  #  to devserver_dir  to keep these unbroken. For now.
    archive_dir = options.archive_dir
    if not os.path.isabs(archive_dir):
      archive_dir = os.path.realpath(os.path.join(devserver_dir, archive_dir))
    _PrepareToServeUpdatesOnly(archive_dir, static_dir)
    static_dir = os.path.realpath(archive_dir)
    serve_only = True

  cache_dir = os.path.join(static_dir, 'cache')
  # If our devserver is only supposed to serve payloads, we shouldn't be mucking
  # with the cache at all. If the devserver hadn't previously generated a cache
  # and is expected, the caller is using it wrong.
  if serve_only:
    # Extra check to make sure we're not being called incorrectly.
    if (options.clear_cache or options.exit or options.pregenerate_update or
        options.board or options.image):
      parser.error('Incompatible flags detected for serve_only mode.')

  elif os.path.exists(cache_dir):
    _CleanCache(cache_dir, options.clear_cache)
  else:
    os.makedirs(cache_dir)

  _Log('Using cache directory %s' % cache_dir)
  _Log('Data dir is %s' % options.data_dir)
  _Log('Source root is %s' % root_dir)
  _Log('Serving from %s' % static_dir)

  # We allow global use here to share with cherrypy classes.
  # pylint: disable=W0603
  global updater
  updater = autoupdate.Autoupdate(
      root_dir=root_dir,
      static_dir=static_dir,
      serve_only=serve_only,
      urlbase=options.urlbase,
      test_image=options.test_image,
      forced_image=options.image,
      payload_path=options.payload,
      proxy_port=options.proxy_port,
      src_image=options.src_image,
      vm=options.vm,
      board=options.board,
      copy_to_static_root=not options.exit,
      private_key=options.private_key,
      critical_update=options.critical_update,
      remote_payload=options.remote_payload,
      max_updates=options.max_updates,
      host_log=options.host_log,
  )

  if options.pregenerate_update:
    updater.PreGenerateUpdate()

  # If the command line requested after setup, it's time to do it.
  if not options.exit:
    # Handle options that must be set globally in cherrypy.
    if options.production:
      cherrypy.config.update({'environment': 'production'})
    if not options.logfile:
      cherrypy.config.update({'log.screen': True})
    else:
      cherrypy.config.update({'log.error_file': options.logfile,
                              'log.access_file': options.logfile})

    cherrypy.quickstart(DevServerRoot(), config=_GetConfig(options))


if __name__ == '__main__':
  main()
