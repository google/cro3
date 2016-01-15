#!/usr/bin/python2

# Copyright (c) 2009-2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Chromium OS development server that can be used for all forms of update.

This devserver can be used to perform system-wide autoupdate and update
of specific portage packages on devices running Chromium OS derived operating
systems. It mainly operates in two modes:

1) archive mode: In this mode, the devserver is configured to stage and
serve artifacts from Google Storage using the credentials provided to it before
it is run. The easiest way to understand this is that the devserver is
functioning as a local cache for artifacts produced and uploaded by build
servers. Users of this form of devserver can either download the artifacts
from the devservers static directory OR use the update RPC to perform a
system-wide autoupdate. Archive mode is always active.

2) artifact-generation mode: in this mode, the devserver will attempt to
generate update payloads and build artifacts when requested. This mode only
works in the Chromium OS chroot as it uses build tools only present in the
chroot (emerge, cros_generate_update_payload, etc.). By default, when a device
requests an update from this form of devserver, the devserver will attempt to
discover if a more recent build of the board has been built by the developer
and generate a payload that the requested system can autoupdate to. In addition,
it accepts gmerge requests from devices that will stage the newest version of
a particular package from a developer's chroot onto a requesting device.

For example:
gmerge gmerge -d <devserver_url>

devserver will see if a newer package of gmerge is available. If gmerge is
cros_work'd on, it will re-build gmerge. After this, gmerge will install that
version of gmerge that the devserver just created/found.

For autoupdates, there are many more advanced options that can help specify
how to update and which payload to give to a requester.
"""

from __future__ import print_function

import json
import optparse
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
from logging import handlers

import cherrypy
from cherrypy import _cplogging as cplogging
from cherrypy.process import plugins

import autoupdate
import build_artifact
import cherrypy_ext
import common_util
import devserver_constants
import downloader
import gsutil_util
import log_util
import xbuddy

# Module-local log function.
def _Log(message, *args):
  return log_util.LogWithTag('DEVSERVER', message, *args)

try:
  import psutil
except ImportError:
  # Ignore psutil import failure. This is for backwards compatibility, so
  # "cros flash" can still update duts with build without psutil installed.
  # The reason is that, during cros flash, local devserver code is copied over
  # to DUT, and devserver will be running inside DUT to stage the build.
  _Log('Python module psutil is not installed, devserver load data will not be '
       'collected')
  psutil = None
except OSError as e:
  # Ignore error like following. psutil may not work properly in builder. Ignore
  # the error as load information of devserver is not used in builder.
  # OSError: [Errno 2] No such file or directory: '/dev/pts/0'
  _Log('psutil is failed to be imported, error: %s. devserver load data will '
       'not be collected.', e)
  psutil = None

try:
  import android_build
except ImportError as e:
  # Ignore android_build import failure. This is to support devserver running
  # inside a ChromeOS device triggered by cros flash. Most ChromeOS test images
  # do not have google-api-python-client module and they don't need to support
  # Android updating, therefore, ignore the import failure here.
  _Log('Import module android_build failed with error: %s', e)
  android_build = None

CACHED_ENTRIES = 12

TELEMETRY_FOLDER = 'telemetry_src'
TELEMETRY_DEPS = ['dep-telemetry_dep.tar.bz2',
                  'dep-page_cycler_dep.tar.bz2',
                  'dep-chrome_test.tar.bz2',
                  'dep-perf_data_dep.tar.bz2']

# Sets up global to share between classes.
updater = None

# Log rotation parameters.  These settings correspond to once a week
# at midnight between Friday and Saturday, with about three months
# of old logs kept for backup.
#
# For more, see the documentation for
# logging.handlers.TimedRotatingFileHandler
_LOG_ROTATION_TIME = 'W4'
_LOG_ROTATION_BACKUP = 13

# Number of seconds between the collection of disk and network IO counters.
STATS_INTERVAL = 10.0

class DevServerError(Exception):
  """Exception class used by this module."""


def require_psutil():
  """Decorator for functions require psutil to run."""
  def deco_require_psutil(func):
    """Wrapper of the decorator function.

    Args:
      func: function to be called.
    """
    def func_require_psutil(*args, **kwargs):
      """Decorator for functions require psutil to run.

      If psutil is not installed, skip calling the function.

      Args:
        *args: arguments for function to be called.
        **kwargs: keyword arguments for function to be called.
      """
      if psutil:
        return func(*args, **kwargs)
      else:
        _Log('Python module psutil is not installed. Function call %s is '
             'skipped.' % func)
    return func_require_psutil
  return deco_require_psutil


def _canonicalize_archive_url(archive_url):
  """Canonicalizes archive_url strings.

  Raises:
    DevserverError: if archive_url is not set.
  """
  if archive_url:
    if not archive_url.startswith('gs://'):
      raise DevServerError("Archive URL isn't from Google Storage (%s) ." %
                           archive_url)

    return archive_url.rstrip('/')
  else:
    raise DevServerError("Must specify an archive_url in the request")


def _canonicalize_local_path(local_path):
  """Canonicalizes |local_path| strings.

  Raises:
    DevserverError: if |local_path| is not set.
  """
  # Restrict staging of local content to only files within the static
  # directory.
  local_path = os.path.abspath(local_path)
  if not local_path.startswith(updater.static_dir):
    raise DevServerError('Local path %s must be a subdirectory of the static'
                         ' directory: %s' % (local_path, updater.static_dir))

  return local_path.rstrip('/')


def _get_artifacts(kwargs):
  """Returns a tuple of named and file artifacts given the stage rpc kwargs.

  Raises:
    DevserverError if no artifacts would be returned.
  """
  artifacts = kwargs.get('artifacts')
  files = kwargs.get('files')
  if not artifacts and not files:
    raise DevServerError('No artifacts specified.')

  # Note we NEED to coerce files to a string as we get raw unicode from
  # cherrypy and we treat files as strings elsewhere in the code.
  return (str(artifacts).split(',') if artifacts else [],
          str(files).split(',') if files else [])


def _is_android_build_request(kwargs):
  """Check if a devserver call is for Android build, based on the arguments.

  This method exams the request's arguments (os_type) to determine if the
  request is for Android build. If os_type is set to `android`, returns True.
  If os_type is not set or has other values, returns False.

  Args:
    kwargs: Keyword arguments for the request.

  Returns:
    True if the request is for Android build. False otherwise.
  """
  os_type = kwargs.get('os_type', None)
  return os_type == 'android'


def _get_downloader(kwargs):
  """Returns the downloader based on passed in arguments.

  Args:
      kwargs: Keyword arguments for the request.
  """
  local_path = kwargs.get('local_path')
  if local_path:
    local_path = _canonicalize_local_path(local_path)

  dl = None
  if local_path:
    dl = downloader.LocalDownloader(updater.static_dir, local_path)

  if not _is_android_build_request(kwargs):
    archive_url = kwargs.get('archive_url')
    if not archive_url and not local_path:
      raise DevServerError('Requires archive_url or local_path to be '
                           'specified.')
    if archive_url and local_path:
      raise DevServerError('archive_url and local_path can not both be '
                           'specified.')
    if not dl:
      archive_url = _canonicalize_archive_url(archive_url)
      dl = downloader.GoogleStorageDownloader(updater.static_dir, archive_url)
  elif not dl:
    target = kwargs.get('target', None)
    branch = kwargs.get('branch', None)
    build_id = kwargs.get('build_id', None)
    if not target or not branch or not build_id:
      raise DevServerError(
          'target, branch, build ID must all be specified for downloading '
          'Android build.')
    dl = downloader.AndroidBuildDownloader(updater.static_dir, branch, build_id,
                                           target)

  return dl


def _get_downloader_and_factory(kwargs):
  """Returns the downloader and artifact factory based on passed in arguments.

  Args:
      kwargs: Keyword arguments for the request.
  """
  artifacts, files = _get_artifacts(kwargs)
  dl = _get_downloader(kwargs)

  if (isinstance(dl, downloader.GoogleStorageDownloader) or
      isinstance(dl, downloader.LocalDownloader)):
    factory_class = build_artifact.ChromeOSArtifactFactory
  elif isinstance(dl, downloader.AndroidBuildDownloader):
    factory_class = build_artifact.AndroidArtifactFactory
  else:
    raise DevServerError('Unrecognized value for downloader type: %s' %
                         type(dl))

  factory = factory_class(dl.GetBuildDir(), artifacts, files, dl.GetBuild())

  return dl, factory


def _LeadingWhiteSpaceCount(string):
  """Count the amount of leading whitespace in a string.

  Args:
    string: The string to count leading whitespace in.

  Returns:
    number of white space chars before characters start.
  """
  matched = re.match(r'^\s+', string)
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


def _GetUpdateTimestampHandler(static_dir):
  """Returns a handler to update directory staged.timestamp.

  This handler resets the stage.timestamp whenever static content is accessed.

  Args:
    static_dir: Directory from which static content is being staged.

  Returns:
      A cherrypy handler to update the timestamp of accessed content.
  """
  def UpdateTimestampHandler():
    if not '404' in cherrypy.response.status:
      build_match = re.match(devserver_constants.STAGED_BUILD_REGEX,
                             cherrypy.request.path_info)
      if build_match:
        build_dir = os.path.join(static_dir, build_match.group('build'))
        downloader.Downloader.TouchTimestampForStaged(build_dir)
  return UpdateTimestampHandler


def _GetConfig(options):
  """Returns the configuration for the devserver."""

  socket_host = '::'
  # Fall back to IPv4 when python is not configured with IPv6.
  if not socket.has_ipv6:
    socket_host = '0.0.0.0'

  # Adds the UpdateTimestampHandler to cherrypy's tools. This tools executes
  # on the on_end_resource hook. This hook is called once processing is
  # complete and the response is ready to be returned.
  cherrypy.tools.update_timestamp = cherrypy.Tool(
      'on_end_resource', _GetUpdateTimestampHandler(options.static_dir))

  base_config = {'global':
                 {'server.log_request_headers': True,
                  'server.protocol_version': 'HTTP/1.1',
                  'server.socket_host': socket_host,
                  'server.socket_port': int(options.port),
                  'response.timeout': 6000,
                  'request.show_tracebacks': True,
                  'server.socket_timeout': 60,
                  'server.thread_pool': 2,
                  'engine.autoreload.on': False,
                 },
                 '/api':
                 {
                  # Gets rid of cherrypy parsing post file for args.
                  'request.process_request_body': False,
                 },
                 '/build':
                 {'response.timeout': 100000,
                 },
                 '/update':
                 {
                  # Gets rid of cherrypy parsing post file for args.
                  'request.process_request_body': False,
                  'response.timeout': 10000,
                 },
                 # Sets up the static dir for file hosting.
                 '/static':
                 {'tools.staticdir.dir': options.static_dir,
                  'tools.staticdir.on': True,
                  'response.timeout': 10000,
                  'tools.update_timestamp.on': True,
                 },
               }
  if options.production:
    base_config['global'].update({'server.thread_pool': 150})
    # TODO(sosa): Do this more cleanly.
    gsutil_util.GSUTIL_ATTEMPTS = 5

  return base_config


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
  if method and type(method) == types.FunctionType and _IsExposed(method):
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
    raise common_util.DevServerHTTPError(400, 'No label provided.')


  @cherrypy.expose
  def fileinfo(self, *args):
    """Returns information about a given staged file.

    Args:
      args: path to the file inside the server's static staging directory

    Returns:
      A JSON encoded dictionary with information about the said file, which may
      contain the following keys/values:
        size (int):      the file size in bytes
        sha1 (string):   a base64 encoded SHA1 hash
        sha256 (string): a base64 encoded SHA256 hash

    Example URL:
      http://myhost/api/fileinfo/some/path/to/file
    """
    file_path = os.path.join(updater.static_dir, *args)
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

  # Number of threads that devserver is staging images.
  _staging_thread_count = 0
  # Lock used to lock increasing/decreasing count.
  _staging_thread_count_lock = threading.Lock()

  @require_psutil()
  def _refresh_io_stats(self):
    """A call running in a thread to update IO stats periodically."""
    prev_disk_io_counters = psutil.disk_io_counters()
    prev_network_io_counters = psutil.net_io_counters()
    prev_read_time = time.time()
    while True:
      time.sleep(STATS_INTERVAL)
      now = time.time()
      interval = now - prev_read_time
      prev_read_time = now
      # Disk IO is for all disks.
      disk_io_counters = psutil.disk_io_counters()
      network_io_counters = psutil.net_io_counters()

      self.disk_read_bytes_per_sec = (
          disk_io_counters.read_bytes -
          prev_disk_io_counters.read_bytes)/interval
      self.disk_write_bytes_per_sec = (
          disk_io_counters.write_bytes -
          prev_disk_io_counters.write_bytes)/interval
      prev_disk_io_counters = disk_io_counters

      self.network_sent_bytes_per_sec = (
          network_io_counters.bytes_sent -
          prev_network_io_counters.bytes_sent)/interval
      self.network_recv_bytes_per_sec = (
          network_io_counters.bytes_recv -
          prev_network_io_counters.bytes_recv)/interval
      prev_network_io_counters = network_io_counters

  @require_psutil()
  def _start_io_stat_thread(self):
    """Start the thread to collect IO stats."""
    thread = threading.Thread(target=self._refresh_io_stats)
    thread.daemon = True
    thread.start()

  def __init__(self, _xbuddy):
    self._builder = None
    self._telemetry_lock_dict = common_util.LockDict()
    self._xbuddy = _xbuddy

    # Cache of disk IO stats, a thread refresh the stats every 10 seconds.
    # lock is not used for these variables as the only thread writes to these
    # variables is _refresh_io_stats.
    self.disk_read_bytes_per_sec = 0
    self.disk_write_bytes_per_sec = 0
    # Cache of network IO stats.
    self.network_sent_bytes_per_sec = 0
    self.network_recv_bytes_per_sec = 0
    self._start_io_stat_thread()

  @cherrypy.expose
  def build(self, board, pkg, **kwargs):
    """Builds the package specified."""
    import builder
    if self._builder is None:
      self._builder = builder.Builder()
    return self._builder.Build(board, pkg, kwargs)

  @cherrypy.expose
  def is_staged(self, **kwargs):
    """Check if artifacts have been downloaded.

      async: True to return without waiting for download to complete.
      artifacts: Comma separated list of named artifacts to download.
        These are defined in artifact_info and have their implementation
        in build_artifact.py.
      files: Comma separated list of file artifacts to stage. These
        will be available as is in the corresponding static directory with no
        custom post-processing.

    returns: True of all artifacts are staged.

    Example:
      To check if autotest and test_suites are staged:
        http://devserver_url:<port>/is_staged?archive_url=gs://your_url/path&
            artifacts=autotest,test_suites
    """
    dl, factory = _get_downloader_and_factory(kwargs)
    return str(dl.IsStaged(factory))

  @cherrypy.expose
  def list_image_dir(self, **kwargs):
    """Take an archive url and list the contents in its staged directory.

    Args:
      kwargs:
        archive_url: Google Storage URL for the build.

    Example:
      To list the contents of where this devserver should have staged
      gs://image-archive/<board>-release/<build> call:
      http://devserver_url:<port>/list_image_dir?archive_url=<gs://..>

    Returns:
      A string with information about the contents of the image directory.
    """
    dl = _get_downloader(kwargs)
    try:
      image_dir_contents = dl.ListBuildDir()
    except build_artifact.ArtifactDownloadError as e:
      return 'Cannot list the contents of staged artifacts. %s' % e
    if not image_dir_contents:
      return '%s has not been staged on this devserver.' % dl.DescribeSource()
    return image_dir_contents

  @cherrypy.expose
  def stage(self, **kwargs):
    """Downloads and caches build artifacts.

    Downloads and caches build artifacts, possibly from a Google Storage URL,
    or from Android's build server. Returns once these have been downloaded
    on the devserver. A call to this will attempt to cache non-specified
    artifacts in the background for the given from the given URL following
    the principle of spatial locality. Spatial locality of different
    artifacts is explicitly defined in the build_artifact module.

    These artifacts will then be available from the static/ sub-directory of
    the devserver.

    Args:
      archive_url: Google Storage URL for the build.
      local_path: Local path for the build.
      async: True to return without waiting for download to complete.
      artifacts: Comma separated list of named artifacts to download.
        These are defined in artifact_info and have their implementation
        in build_artifact.py.
      files: Comma separated list of files to stage. These
        will be available as is in the corresponding static directory with no
        custom post-processing.
      clean: True to remove any previously staged artifacts first.

    Example:
      To download the autotest and test suites tarballs:
        http://devserver_url:<port>/stage?archive_url=gs://your_url/path&
            artifacts=autotest,test_suites
      To download the full update payload:
        http://devserver_url:<port>/stage?archive_url=gs://your_url/path&
            artifacts=full_payload
      To download just a file called blah.bin:
        http://devserver_url:<port>/stage?archive_url=gs://your_url/path&
            files=blah.bin

      For both these examples, one could find these artifacts at:
        http://devserver_url:<port>/static/<relative_path>*

      Note for this example, relative path is the archive_url stripped of its
      basename i.e. path/ in the examples above. Specific example:

      gs://chromeos-image-archive/x86-mario-release/R26-3920.0.0

      Will get staged to:

      http://devserver_url:<port>/static/x86-mario-release/R26-3920.0.0
    """
    dl, factory = _get_downloader_and_factory(kwargs)

    with DevServerRoot._staging_thread_count_lock:
      DevServerRoot._staging_thread_count += 1
    try:
      boolean_string = kwargs.get('clean')
      clean = xbuddy.XBuddy.ParseBoolean(boolean_string)
      if clean and os.path.exists(dl.GetBuildDir()):
        _Log('Removing %s' % dl.GetBuildDir())
        shutil.rmtree(dl.GetBuildDir())
      async = kwargs.get('async', False)
      dl.Download(factory, async=async)
    finally:
      with DevServerRoot._staging_thread_count_lock:
        DevServerRoot._staging_thread_count -= 1
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
    dl = _get_downloader(kwargs)

    build_path = dl.GetBuildDir()
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
        if not os.path.exists(dep_path):
          # This dep does not exist (could be new), do not extract it.
          continue
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
        raise DevServerError(
            'Failure in telemetry setup for build %s. Appears that the '
            'test_src to src move failed.' % dl.GetBuild())

      return src_folder

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
    kwargs['artifacts'] = 'symbols'
    dl = _get_downloader(kwargs)

    # Ensure the symbols have been staged.
    if self.stage(**kwargs) != 'Success':
      raise DevServerError('Failed to stage symbols for %s' %
                           dl.DescribeSource())

    to_return = ''
    with tempfile.NamedTemporaryFile() as local:
      while True:
        data = minidump.file.read(8192)
        if not data:
          break
        local.write(data)

      local.flush()

      symbols_directory = os.path.join(dl.GetBuildDir(), 'debug', 'breakpad')

      stackwalk = subprocess.Popen(
          ['minidump_stackwalk', local.name, symbols_directory],
          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

      to_return, error_text = stackwalk.communicate()
      if stackwalk.returncode != 0:
        raise DevServerError("Can't generate stack trace: %s (rc=%d)" % (
            error_text, stackwalk.returncode))

    return to_return

  @cherrypy.expose
  def latestbuild(self, **kwargs):
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
    if not kwargs:
      return _PrintDocStringAsHTML(self.latestbuild)

    if 'target' not in kwargs:
      raise common_util.DevServerHTTPError(500, 'Error: target= is required!')

    if _is_android_build_request(kwargs):
      branch = kwargs.get('branch', None)
      target = kwargs.get('target', None)
      if not target or not branch:
        raise DevServerError(
          'Both target and branch must be specified to query for the latest '
          'Android build.')
      return android_build.BuildAccessor.GetLatestBuildID(target, branch)

    try:
      return common_util.GetLatestBuildVersion(
          updater.static_dir, kwargs['target'],
          milestone=kwargs.get('milestone'))
    except common_util.CommonUtilError as errmsg:
      raise common_util.DevServerHTTPError(500, str(errmsg))

  @cherrypy.expose
  def controlfiles(self, **kwargs):
    """Return a control file or a list of all known control files.

    Example URL:
      To List all control files:
      http://dev-server/controlfiles?suite_name=&build=daisy_spring-release/R29-4279.0.0
      To List all control files for, say, the bvt suite:
      http://dev-server/controlfiles?suite_name=bvt&build=daisy_spring-release/R29-4279.0.0
      To return the contents of a path:
      http://dev-server/controlfiles?board=x86-alex-release&build=R18-1514.0.0&control_path=client/sleeptest/control

    Args:
      build: The build i.e. x86-alex-release/R18-1514.0.0-a1-b1450.
      control_path: If you want the contents of a control file set this
        to the path. E.g. client/site_tests/sleeptest/control
        Optional, if not provided return a list of control files is returned.
      suite_name: If control_path is not specified but a suite_name is
        specified, list the control files belonging to that suite instead of
        all control files. The empty string for suite_name will list all control
        files for the build.

    Returns:
      Contents of a control file if control_path is provided.
      A list of control files if no control_path is provided.
    """
    if not kwargs:
      return _PrintDocStringAsHTML(self.controlfiles)

    if 'build' not in kwargs:
      raise common_util.DevServerHTTPError(500, 'Error: build= is required!')

    if 'control_path' not in kwargs:
      if 'suite_name' in kwargs and kwargs['suite_name']:
        return common_util.GetControlFileListForSuite(
            updater.static_dir, kwargs['build'], kwargs['suite_name'])
      else:
        return common_util.GetControlFileList(
            updater.static_dir, kwargs['build'])
    else:
      return common_util.GetControlFile(
          updater.static_dir, kwargs['build'], kwargs['control_path'])

  @cherrypy.expose
  def xbuddy_translate(self, *args, **kwargs):
    """Translates an xBuddy path to a real path to artifact if it exists.

    Args:
      args: An xbuddy path in the form of {local|remote}/build_id/artifact.
        Local searches the devserver's static directory. Remote searches a
        Google Storage image archive.

    Kwargs:
      image_dir: Google Storage image archive to search in if requesting a
        remote artifact. If none uses the default bucket.

    Returns:
      String in the format of build_id/artifact as stored on the local server
      or in Google Storage.
    """
    build_id, filename = self._xbuddy.Translate(
        args, image_dir=kwargs.get('image_dir'))
    response = os.path.join(build_id, filename)
    _Log('Path translation requested, returning: %s', response)
    return response

  @cherrypy.expose
  def xbuddy(self, *args, **kwargs):
    """The full xBuddy call, returns resource specified by path_parts.

    Args:
      path_parts: the path following xbuddy/ in the call url is split into the
        components of the path. The path can be understood as
        "{local|remote}/build_id/artifact" where build_id is composed of
        "board/version."

        The first path element is optional, and can be "remote" or "local"
          If local (the default), devserver will not attempt to access Google
          Storage, and will only search the static directory for the files.
          If remote, devserver will try to obtain the artifact off GS if it's
          not found locally.
        The board is the familiar board name, optionally suffixed.
        The version can be the google storage version number, and may also be
          any of a number of xBuddy defined version aliases that will be
          translated into the latest built image that fits the description.
          Defaults to latest.
        The artifact is one of a number of image or artifact aliases used by
          xbuddy, defined in xbuddy:ALIASES. Defaults to test.

    Kwargs:
      for_update: {true|false}
                  if true, pregenerates the update payloads for the image,
                  and returns the update uri to pass to the
                  update_engine_client.
      return_dir: {true|false}
                  if set to true, returns the url to the update.gz
      relative_path: {true|false}
                     if set to true, returns the relative path to the payload
                     directory from static_dir.
    Example URL:
      http://host:port/xbuddy/x86-generic/R26-4000.0.0/test
      or
      http://host:port/xbuddy/x86-generic/R26-4000.0.0/test?return_dir=true

    Returns:
      If |for_update|, returns a redirect to the image or update file
      on the devserver. E.g.,
        http://host:port/static/archive/x86-generic-release/R26-4000.0.0/
            chromium-test-image.bin
      If |return_dir|, return a uri to the folder where the artifact is. E.g.,
        http://host:port/static/x86-generic-release/R26-4000.0.0/
      If |relative_path| is true, return a relative path the folder where the
      payloads are. E.g.,
        archive/x86-generic-release/R26-4000.0.0
    """
    boolean_string = kwargs.get('for_update')
    for_update = xbuddy.XBuddy.ParseBoolean(boolean_string)
    boolean_string = kwargs.get('return_dir')
    return_dir = xbuddy.XBuddy.ParseBoolean(boolean_string)
    boolean_string = kwargs.get('relative_path')
    relative_path = xbuddy.XBuddy.ParseBoolean(boolean_string)

    if return_dir and relative_path:
      raise common_util.DevServerHTTPError(
          500, 'Cannot specify both return_dir and relative_path')

    # For updates, we optimize downloading of test images.
    file_name = None
    build_id = None
    if for_update:
      try:
        build_id = self._xbuddy.StageTestArtifactsForUpdate(args)
      except build_artifact.ArtifactDownloadError:
        build_id = None

    if not build_id:
      build_id, file_name = self._xbuddy.Get(args)

    if for_update:
      _Log('Payload generation triggered by request')
      # Forces payload to be in cache and symlinked into build_id dir.
      updater.GetUpdateForLabel(autoupdate.FORCED_UPDATE, build_id,
                                image_name=file_name)

    response = None
    if return_dir:
      response = os.path.join(cherrypy.request.base, 'static', build_id)
      _Log('Directory requested, returning: %s', response)
    elif relative_path:
      response = build_id
      _Log('Relative path requested, returning: %s', response)
    elif for_update:
      response = os.path.join(cherrypy.request.base, 'update', build_id)
      _Log('Update URI requested, returning: %s', response)
    else:
      # Redirect to download the payload if no kwargs are set.
      build_id = '/' + os.path.join('static', build_id, file_name)
      _Log('Payload requested, returning: %s', build_id)
      raise cherrypy.HTTPRedirect(build_id, 302)

    return response

  @cherrypy.expose
  def xbuddy_list(self):
    """Lists the currently available images & time since last access.

    Returns:
      A string representation of a list of tuples [(build_id, time since last
      access),...]
    """
    return self._xbuddy.List()

  @cherrypy.expose
  def xbuddy_capacity(self):
    """Returns the number of images cached by xBuddy."""
    return self._xbuddy.Capacity()

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

    This request can be handled in one of 4 ways, depending on the devsever
    settings and intermediate path.

    1. No intermediate path
    If no intermediate path is given, the default behavior is to generate an
    update payload from the latest test image locally built for the board
    specified in the xml. Devserver serves the generated payload.

    2. Path explicitly invokes XBuddy
    If there is a path given, it can explicitly invoke xbuddy by prefixing it
    with 'xbuddy'. This path is then used to acquire an image binary for the
    devserver to generate an update payload from. Devserver then serves this
    payload.

    3. Path is left for the devserver to interpret.
    If the path given doesn't explicitly invoke xbuddy, devserver will attempt
    to generate a payload from the test image in that directory and serve it.

    4. The devserver is in a 'forced' mode. TO BE DEPRECATED
    This comes from the usage of --forced_payload or --image when starting the
    devserver. No matter what path (or no path) gets passed in, devserver will
    serve the update payload (--forced_payload) or generate an update payload
    from the image (--image).

    Examples:
      1. No intermediate path
      update_engine_client --omaha_url=http://myhost/update
      This generates an update payload from the latest test image locally built
      for the board specified in the xml.

      2. Explicitly invoke xbuddy
      update_engine_client --omaha_url=
      http://myhost/update/xbuddy/remote/board/version/dev
      This would go to GS to download the dev image for the board, from which
      the devserver would generate a payload to serve.

      3. Give a path for devserver to interpret
      update_engine_client --omaha_url=http://myhost/update/some/random/path
      This would attempt, in order to:
        a) Generate an update from a test image binary if found in
           static_dir/some/random/path.
        b) Serve an update payload found in static_dir/some/random/path.
        c) Hope that some/random/path takes the form "board/version" and
           and attempt to download an update payload for that board/version
           from GS.
    """
    label = '/'.join(args)
    body_length = int(cherrypy.request.headers.get('Content-Length', 0))
    data = cherrypy.request.rfile.read(body_length)

    return updater.HandleUpdatePing(data, label)

  @require_psutil()
  def _get_io_stats(self):
    """Get the IO stats as a dictionary.

    Returns:
      A dictionary of IO stats collected by psutil.

    """
    return {'disk_read_bytes_per_second': self.disk_read_bytes_per_sec,
            'disk_write_bytes_per_second': self.disk_write_bytes_per_sec,
            'disk_total_bytes_per_second': (self.disk_read_bytes_per_sec +
                                            self.disk_write_bytes_per_sec),
            'network_sent_bytes_per_second': self.network_sent_bytes_per_sec,
            'network_recv_bytes_per_second': self.network_recv_bytes_per_sec,
            'network_total_bytes_per_second': (self.network_sent_bytes_per_sec +
                                               self.network_recv_bytes_per_sec),
            'cpu_percent': psutil.cpu_percent(),}

  @cherrypy.expose
  def check_health(self):
    """Collect the health status of devserver to see if it's ready for staging.

    Returns:
      A JSON dictionary containing all or some of the following fields:
      free_disk (int):            free disk space in GB
      staging_thread_count (int): number of devserver threads currently staging
                                  an image
    """
    # Get free disk space.
    stat = os.statvfs(updater.static_dir)
    free_disk = stat.f_bsize * stat.f_bavail / 1000000000

    health_data = {
        'free_disk': free_disk,
        'staging_thread_count': DevServerRoot._staging_thread_count}
    health_data.update(self._get_io_stats() or {})

    return json.dumps(health_data)


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


def _AddTestingOptions(parser):
  group = optparse.OptionGroup(
      parser, 'Advanced Testing Options', 'These are used by test scripts and '
      'developers writing integration tests utilizing the devserver. They are '
      'not intended to be really used outside the scope of someone '
      'knowledgable about the test.')
  group.add_option('--exit',
                   action='store_true',
                   help='do not start the server (yet pregenerate/clear cache)')
  group.add_option('--host_log',
                   action='store_true', default=False,
                   help='record history of host update events (/api/hostlog)')
  group.add_option('--max_updates',
                   metavar='NUM', default=-1, type='int',
                   help='maximum number of update checks handled positively '
                        '(default: unlimited)')
  group.add_option('--private_key',
                   metavar='PATH', default=None,
                   help='path to the private key in pem format. If this is set '
                   'the devserver will generate update payloads that are '
                   'signed with this key.')
  group.add_option('--private_key_for_metadata_hash_signature',
                   metavar='PATH', default=None,
                   help='path to the private key in pem format. If this is set '
                   'the devserver will sign the metadata hash with the given '
                   'key and transmit in the Omaha-style XML response.')
  group.add_option('--public_key',
                   metavar='PATH', default=None,
                   help='path to the public key in pem format. If this is set '
                   'the devserver will transmit a base64 encoded version of '
                   'the content in the Omaha-style XML response.')
  group.add_option('--proxy_port',
                   metavar='PORT', default=None, type='int',
                   help='port to have the client connect to -- basically the '
                   'devserver lies to the update to tell it to get the payload '
                   'from a different port that will proxy the request back to '
                   'the devserver. The proxy must be managed outside the '
                   'devserver.')
  group.add_option('--remote_payload',
                   action='store_true', default=False,
                   help='Payload is being served from a remote machine. With '
                   'this setting enabled, this devserver instance serves as '
                   'just an Omaha server instance. In this mode, the '
                   'devserver enforces a few extra components of the Omaha '
                   'protocol, such as hardware class, being sent.')
  group.add_option('-u', '--urlbase',
                   metavar='URL',
                   help='base URL for update images, other than the '
                   'devserver. Use in conjunction with remote_payload.')
  parser.add_option_group(group)


def _AddUpdateOptions(parser):
  group = optparse.OptionGroup(
      parser, 'Autoupdate Options', 'These options can be used to change '
      'how the devserver either generates or serve update payloads. Please '
      'note that all of these option affect how a payload is generated and so '
      'do not work in archive-only mode.')
  group.add_option('--board',
                   help='By default the devserver will create an update '
                   'payload from the latest image built for the board '
                   'a device that is requesting an update has. When we '
                   'pre-generate an update (see below) and we do not specify '
                   'another update_type option like image or payload, the '
                   'devserver needs to know the board to generate the latest '
                   'image for. This is that board.')
  group.add_option('--critical_update',
                   action='store_true', default=False,
                   help='Present update payload as critical')
  group.add_option('--image',
                   metavar='FILE',
                   help='Generate and serve an update using this image to any '
                   'device that requests an update.')
  group.add_option('--payload',
                   metavar='PATH',
                   help='use the update payload from specified directory '
                   '(update.gz).')
  group.add_option('-p', '--pregenerate_update',
                   action='store_true', default=False,
                   help='pre-generate the update payload before accepting '
                   'update requests. Useful to help debug payload generation '
                   'issues quickly. Also if an update payload will take a '
                   'long time to generate, a client may timeout if you do not'
                   'pregenerate the update.')
  group.add_option('--src_image',
                   metavar='PATH', default='',
                   help='If specified, delta updates will be generated using '
                   'this image as the source image. Delta updates are when '
                   'you are updating from a "source image" to a another '
                   'image.')
  parser.add_option_group(group)


def _AddProductionOptions(parser):
  group = optparse.OptionGroup(
      parser, 'Advanced Server Options', 'These options can be used to changed '
      'for advanced server behavior.')
  group.add_option('--clear_cache',
                   action='store_true', default=False,
                   help='At startup, removes all cached entries from the'
                   'devserver\'s cache.')
  group.add_option('--logfile',
                   metavar='PATH',
                   help='log output to this file instead of stdout')
  group.add_option('--pidfile',
                   metavar='PATH',
                   help='path to output a pid file for the server.')
  group.add_option('--portfile',
                   metavar='PATH',
                   help='path to output the port number being served on.')
  group.add_option('--production',
                   action='store_true', default=False,
                   help='have the devserver use production values when '
                   'starting up. This includes using more threads and '
                   'performing less logging.')
  parser.add_option_group(group)


def _MakeLogHandler(logfile):
  """Create a LogHandler instance used to log all messages."""
  hdlr_cls = handlers.TimedRotatingFileHandler
  hdlr = hdlr_cls(logfile, when=_LOG_ROTATION_TIME,
                  backupCount=_LOG_ROTATION_BACKUP)
  hdlr.setFormatter(cplogging.logfmt)
  return hdlr


def main():
  usage = '\n\n'.join(['usage: %prog [options]', __doc__])
  parser = optparse.OptionParser(usage=usage)

  # get directory that the devserver is run from
  devserver_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
  default_static_dir = '%s/static' % devserver_dir
  parser.add_option('--static_dir',
                    metavar='PATH',
                    default=default_static_dir,
                    help='writable static directory')
  parser.add_option('--port',
                    default=8080, type='int',
                    help=('port for the dev server to use; if zero, binds to '
                          'an arbitrary available port (default: 8080)'))
  parser.add_option('-t', '--test_image',
                    action='store_true',
                    help='Deprecated.')
  parser.add_option('-x', '--xbuddy_manage_builds',
                    action='store_true',
                    default=False,
                    help='If set, allow xbuddy to manage images in'
                    'build/images.')
  parser.add_option('-a', '--android_build_credential',
                    default=None,
                    help='Path to a json file which contains the credential '
                    'needed to access Android builds.')
  _AddProductionOptions(parser)
  _AddUpdateOptions(parser)
  _AddTestingOptions(parser)
  (options, _) = parser.parse_args()

  # Handle options that must be set globally in cherrypy.  Do this
  # work up front, because calls to _Log() below depend on this
  # initialization.
  if options.production:
    cherrypy.config.update({'environment': 'production'})
  if not options.logfile:
    cherrypy.config.update({'log.screen': True})
  else:
    cherrypy.config.update({'log.error_file': '',
                            'log.access_file': ''})
    hdlr = _MakeLogHandler(options.logfile)
    # Pylint can't seem to process these two calls properly
    # pylint: disable=E1101
    cherrypy.log.access_log.addHandler(hdlr)
    cherrypy.log.error_log.addHandler(hdlr)
    # pylint: enable=E1101

  # set static_dir, from which everything will be served
  options.static_dir = os.path.realpath(options.static_dir)

  cache_dir = os.path.join(options.static_dir, 'cache')
  # If our devserver is only supposed to serve payloads, we shouldn't be
  # mucking with the cache at all. If the devserver hadn't previously
  # generated a cache and is expected, the caller is using it wrong.
  if os.path.exists(cache_dir):
    _CleanCache(cache_dir, options.clear_cache)
  else:
    os.makedirs(cache_dir)

  _Log('Using cache directory %s' % cache_dir)
  _Log('Serving from %s' % options.static_dir)

  _xbuddy = xbuddy.XBuddy(options.xbuddy_manage_builds,
                          options.board,
                          static_dir=options.static_dir)
  if options.clear_cache and options.xbuddy_manage_builds:
    _xbuddy.CleanCache()

  # We allow global use here to share with cherrypy classes.
  # pylint: disable=W0603
  global updater
  updater = autoupdate.Autoupdate(
      _xbuddy,
      static_dir=options.static_dir,
      urlbase=options.urlbase,
      forced_image=options.image,
      payload_path=options.payload,
      proxy_port=options.proxy_port,
      src_image=options.src_image,
      board=options.board,
      copy_to_static_root=not options.exit,
      private_key=options.private_key,
      private_key_for_metadata_hash_signature=(
          options.private_key_for_metadata_hash_signature),
      public_key=options.public_key,
      critical_update=options.critical_update,
      remote_payload=options.remote_payload,
      max_updates=options.max_updates,
      host_log=options.host_log,
  )

  if options.pregenerate_update:
    updater.PreGenerateUpdate()

  if options.exit:
    return

  dev_server = DevServerRoot(_xbuddy)

  # Patch CherryPy to support binding to any available port (--port=0).
  cherrypy_ext.ZeroPortPatcher.DoPatch(cherrypy)

  if options.pidfile:
    plugins.PIDFile(cherrypy.engine, options.pidfile).subscribe()

  if options.portfile:
    cherrypy_ext.PortFile(cherrypy.engine, options.portfile).subscribe()

  if (options.android_build_credential and
      os.path.exists(options.android_build_credential)):
    try:
      with open(options.android_build_credential) as f:
        android_build.BuildAccessor.credential_info = json.load(f)
    except ValueError as e:
      _Log('Failed to load the android build credential: %s. Error: %s.' %
           (options.android_build_credential, e))
  cherrypy.quickstart(dev_server, config=_GetConfig(options))


if __name__ == '__main__':
  main()
