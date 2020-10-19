#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright (c) 2009-2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Chromium OS development server that can be used for caching files.

The devserver is configured to stage and serve artifacts from Google Storage
using the credentials provided to it before it is run. The easiest way to
understand this is that the devserver is functioning as a local cache for
artifacts produced and uploaded by build servers. Users of this form of
devserver can download the artifacts from the devservers static directory.
Archive mode is always active.
"""

from __future__ import print_function

import json
import optparse  # pylint: disable=deprecated-module
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import types
from logging import handlers

from six.moves import http_client

# pylint: disable=no-name-in-module, import-error
import cherrypy
from cherrypy import _cplogging as cplogging
from cherrypy.process import plugins
# pylint: enable=no-name-in-module, import-error

import cherrypy_ext
import health_checker

# This must happen before any local modules get a chance to import
# anything from chromite.  Otherwise, really bad things will happen, and
# you will _not_ understand why.
import setup_chromite  # pylint: disable=unused-import
from chromite.lib.xbuddy import android_build
from chromite.lib.xbuddy import artifact_info
from chromite.lib.xbuddy import build_artifact
from chromite.lib.xbuddy import cherrypy_log_util
from chromite.lib.xbuddy import common_util
from chromite.lib.xbuddy import devserver_constants
from chromite.lib.xbuddy import downloader
from chromite.lib.xbuddy import xbuddy

# Module-local log function.
def _Log(message, *args):
  return cherrypy_log_util.LogWithTag('DEVSERVER', message, *args)

CACHED_ENTRIES = 12

TELEMETRY_FOLDER = 'telemetry_src'
TELEMETRY_DEPS = ['dep-telemetry_dep.tar.bz2',
                  'dep-page_cycler_dep.tar.bz2',
                  'dep-chrome_test.tar.bz2',
                  'dep-perf_data_dep.tar.bz2']

# Log rotation parameters.  These settings correspond to twice a day once
# devserver is started, with about two weeks (28 backup files) of old logs
# kept for backup.
#
# For more, see the documentation in standard python library for
# logging.handlers.TimedRotatingFileHandler
_LOG_ROTATION_TIME = 'H'
_LOG_ROTATION_INTERVAL = 12  # hours
_LOG_ROTATION_BACKUP = 28  # backup counts

# Error msg for deprecated RPC usage.
DEPRECATED_RPC_ERROR_MSG = ('The %s RPC has been deprecated. Usage of this '
                            'RPC is discouraged. Please go to '
                            'go/devserver-deprecation for more information.')


class DevServerError(Exception):
  """Exception class used by DevServer."""


class DeprecatedRPCError(DevServerError):
  """Exception class used when an RPC is deprecated but is still being used."""

  def __init__(self, rpc_name):
    """Constructor for DeprecatedRPCError class.

    :param rpc_name: (str) name of the RPC that has been deprecated.
    """
    super(DeprecatedRPCError, self).__init__(
        DEPRECATED_RPC_ERROR_MSG % rpc_name)
    self.rpc_name = rpc_name


class DevServerHTTPError(cherrypy.HTTPError):
  """Exception class to log the HTTPResponse before routing it to cherrypy."""
  def __init__(self, status, message):
    """CherryPy error with logging.

    Args:
      status: HTTPResponse status.
      message: Message associated with the response.
    """
    cherrypy.HTTPError.__init__(self, status, message)
    _Log('HTTPError status: %s message: %s', status, message)


def _canonicalize_archive_url(archive_url):
  """Canonicalizes archive_url strings.

  Raises:
    DevserverError: if archive_url is not set.
  """
  if archive_url:
    if not archive_url.startswith('gs://'):
      raise DevServerError(
          "Archive URL isn't from Google Storage (%s) ." % archive_url)

    return archive_url.rstrip('/')
  else:
    raise DevServerError('Must specify an archive_url in the request')


def _canonicalize_local_path(local_path, static_dir):
  """Canonicalizes |local_path| strings.

  Args:
    local_path: The input path.
    static_dir: Devserver's static cache directory.

  Raises:
    DevserverError: if |local_path| is not set.
  """
  # Restrict staging of local content to only files within the static
  # directory.
  local_path = os.path.abspath(local_path)
  if not local_path.startswith(static_dir):
    raise DevServerError(
        'Local path %s must be a subdirectory of the static'
        ' directory: %s' % (local_path, static_dir))

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


def _get_downloader(static_dir, kwargs):
  """Returns the downloader based on passed in arguments.

  Args:
    static_dir: Devserver's static cache directory.
    kwargs: Keyword arguments for the request.
  """
  local_path = kwargs.get('local_path')
  if local_path:
    local_path = _canonicalize_local_path(local_path, static_dir)

  dl = None
  if local_path:
    delete_source = _parse_boolean_arg(kwargs, 'delete_source')
    dl = downloader.LocalDownloader(static_dir, local_path,
                                    delete_source=delete_source)

  if not _is_android_build_request(kwargs):
    archive_url = kwargs.get('archive_url')
    if not archive_url and not local_path:
      raise DevServerError(
          'Requires archive_url or local_path to be specified.')
    if archive_url and local_path:
      raise DevServerError(
          'archive_url and local_path can not both be specified.')
    if not dl:
      archive_url = _canonicalize_archive_url(archive_url)
      dl = downloader.GoogleStorageDownloader(
          static_dir, archive_url,
          downloader.GoogleStorageDownloader.GetBuildIdFromArchiveURL(
              archive_url))
  elif not dl:
    target = kwargs.get('target', None)
    branch = kwargs.get('branch', None)
    build_id = kwargs.get('build_id', None)
    if not target or not branch or not build_id:
      raise DevServerError('target, branch, build ID must all be specified for '
                           'downloading Android build.')
    dl = downloader.AndroidBuildDownloader(static_dir, branch, build_id,
                                           target)

  return dl


def _get_downloader_and_factory(static_dir, kwargs):
  """Returns the downloader and artifact factory based on passed in arguments.

  Args:
    static_dir: Devserver's static cache directory.
    kwargs: Keyword arguments for the request.
  """
  artifacts, files = _get_artifacts(kwargs)
  dl = _get_downloader(static_dir, kwargs)

  if (isinstance(dl, (downloader.GoogleStorageDownloader,
                      downloader.LocalDownloader))):
    factory_class = build_artifact.ChromeOSArtifactFactory
  elif isinstance(dl, downloader.AndroidBuildDownloader):
    factory_class = build_artifact.AndroidArtifactFactory
  else:
    raise DevServerError(
        'Unrecognized value for downloader type: %s' % type(dl))

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

  base_config = {
      'global': {
          'server.log_request_headers': True,
          'server.protocol_version': 'HTTP/1.1',
          'server.socket_host': socket_host,
          'server.socket_port': int(options.port),
          'response.timeout': 6000,
          'request.show_tracebacks': True,
          'server.socket_timeout': 60,
          'server.thread_pool': 2,
          'engine.autoreload.on': False,
      },
      '/build': {
          'response.timeout': 100000,
      },
      # Sets up the static dir for file hosting.
      '/static': {
          'tools.staticdir.dir': options.static_dir,
          'tools.staticdir.on': True,
          'response.timeout': 10000,
          'tools.update_timestamp.on': True,
      },
  }
  if options.production:
    base_config['global'].update({'server.thread_pool': 150})

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


def _GetExposedMethod(nested_member):
  """Returns a CherryPy-exposed method, if such exists.

  Args:
    nested_member: a slash-joined path to the nested member

  Returns:
    A function object corresponding to the path defined by |nested_member| from
    the app root object registered, if the function is exposed; None otherwise.
  """
  for app in cherrypy.tree.apps.values():
    # Use the 'index' function doc as the doc of the app.
    if nested_member == app.script_name.lstrip('/'):
      nested_member = 'index'

    method = _GetRecursiveMemberObject(app.root, nested_member.split('/'))
    if method and isinstance(method, types.FunctionType) and _IsExposed(method):
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
  for member in root.__class__.__dict__.keys():
    prefixed_member = prefix + '/' + member if prefix else member
    if unlisted and prefixed_member in unlisted:
      continue
    member_obj = root.__class__.__dict__[member]
    if _IsExposed(member_obj):
      if isinstance(member_obj, types.FunctionType):
        # Regard the app name as exposed "method" name if it exposed 'index'
        # function.
        if prefix and member == 'index':
          method_list.append(prefix)
        else:
          method_list.append(prefixed_member)
      else:
        method_list += _FindExposedMethods(
            member_obj, prefixed_member, unlisted)
  return method_list


def _parse_boolean_arg(kwargs, key):
  """Parse boolean arg from kwargs.

  Args:
    kwargs: the parameters to be checked.
    key: the key to be parsed.

  Returns:
    The boolean value of kwargs[key], or False if key doesn't exist in kwargs.

  Raises:
    DevServerHTTPError if kwargs[key] is not a boolean variable.
  """
  if key in kwargs:
    if kwargs[key] == 'True':
      return True
    elif kwargs[key] == 'False':
      return False
    else:
      raise DevServerHTTPError(http_client.INTERNAL_SERVER_ERROR,
                               'The value for key %s is not boolean.' % key)
  else:
    return False


def _parse_string_arg(kwargs, key):
  """Parse string arg from kwargs.

  Args:
    kwargs: the parameters to be checked.
    key: the key to be parsed.

  Returns:
    The string value of kwargs[key], or None if key doesn't exist in kwargs.
  """
  if key in kwargs:
    return kwargs[key]
  else:
    return None


def _build_uri_from_build_name(build_name):
  """Get build url from a given build name.

  Args:
    build_name: the build name to be parsed, whose format is
        'board/release_version'.

  Returns:
    The release_archive_url on Google Storage for this build name.
  """
  # TODO(ahassani): This function doesn't seem to be used anywhere since its
  # previous use of lib.paygen.gspath was broken and it doesn't seem to be
  # causing any runtime issues. So deprecate this in the future.
  tokens = build_name.split('/')
  return 'gs://chromeos-releases/stable-channel/%s/%s' % (tokens[0], tokens[1])


def is_deprecated_server():
  """Gets whether the devserver has deprecated RPCs."""
  return cherrypy.config.get('infra_removal', False)


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

  # Number of threads that devserver is staging images.
  _staging_thread_count = 0
  # Lock used to lock increasing/decreasing count.
  _staging_thread_count_lock = threading.Lock()

  def __init__(self, _xbuddy, static_dir):
    self._builder = None
    self._telemetry_lock_dict = common_util.LockDict()
    self._xbuddy = _xbuddy
    self._static_dir = static_dir

  @property
  def staging_thread_count(self):
    """Get the staging thread count."""
    return self._staging_thread_count

  @cherrypy.expose
  def build(self, board, pkg, **kwargs):
    """Builds the package specified."""
    if is_deprecated_server():
      raise DeprecatedRPCError('build')

    import builder
    if self._builder is None:
      self._builder = builder.Builder()
    return self._builder.Build(board, pkg, kwargs)

  @cherrypy.expose
  def is_staged(self, **kwargs):
    """Check if artifacts have been downloaded.

    Examples:
      To check if autotest and test_suites are staged:
        http://devserver_url:<port>/is_staged?archive_url=gs://your_url/path&
            artifacts=autotest,test_suites

    Args:
      async: True to return without waiting for download to complete.
      artifacts: Comma separated list of named artifacts to download.
        These are defined in artifact_info and have their implementation
        in build_artifact.py.
      files: Comma separated list of file artifacts to stage. These
        will be available as is in the corresponding static directory with no
        custom post-processing.

    Returns:
      True of all artifacts are staged.
    """
    dl, factory = _get_downloader_and_factory(self._static_dir, kwargs)
    response = str(dl.IsStaged(factory))
    _Log('Responding to is_staged %s request with %r', kwargs, response)
    return response

  @cherrypy.expose
  def list_image_dir(self, **kwargs):
    """Take an archive url and list the contents in its staged directory.

    Examples:
      To list the contents of where this devserver should have staged
      gs://image-archive/<board>-release/<build> call:
      http://devserver_url:<port>/list_image_dir?archive_url=<gs://..>

    Args:
      archive_url: Google Storage URL for the build.

    Returns:
      A string with information about the contents of the image directory.
    """
    dl = _get_downloader(self._static_dir, kwargs)
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

    Examples:
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

    Args:
      archive_url: Google Storage URL for the build.
      local_path: Local path for the build.
      delete_source: Only meaningful with local_path. bool to indicate if the
          source files should be deleted. This is especially useful when staging
          a file locally in resource constrained environments as it allows us to
          move the relevant files locally instead of copying them.
      async: True to return without waiting for download to complete.
      artifacts: Comma separated list of named artifacts to download.
        These are defined in artifact_info and have their implementation
        in build_artifact.py.
      files: Comma separated list of files to stage. These
        will be available as is in the corresponding static directory with no
        custom post-processing.
      clean: True to remove any previously staged artifacts first.
    """
    dl, factory = _get_downloader_and_factory(self._static_dir, kwargs)

    with DevServerRoot._staging_thread_count_lock:
      DevServerRoot._staging_thread_count += 1
    try:
      boolean_string = kwargs.get('clean')
      clean = xbuddy.XBuddy.ParseBoolean(boolean_string)
      if clean and os.path.exists(dl.GetBuildDir()):
        _Log('Removing %s' % dl.GetBuildDir())
        shutil.rmtree(dl.GetBuildDir())
      is_async = kwargs.get('async', False)
      dl.Download(factory, is_async=is_async)
    finally:
      with DevServerRoot._staging_thread_count_lock:
        DevServerRoot._staging_thread_count -= 1
    return 'Success'

  @cherrypy.expose
  def locate_file(self, **kwargs):
    """Get the path to the given file name.

    This method looks up the given file name inside specified build artifacts.
    One use case is to help caller to locate an apk file inside a build
    artifact. The location of the apk file could be different based on the
    branch and target.

    Args:
      file_name: Name of the file to look for.
      artifacts: A list of artifact names to search for the file.

    Returns:
      Path to the file with the given name. It's relative to the folder for the
      build, e.g., DATA/priv-app/sl4a/sl4a.apk
    """
    if is_deprecated_server():
      raise DeprecatedRPCError('locate_file')

    dl, _ = _get_downloader_and_factory(self._static_dir, kwargs)
    try:
      file_name = kwargs['file_name']
      artifacts = kwargs['artifacts']
    except KeyError:
      raise DevServerError(
          '`file_name` and `artifacts` are required to search '
          'for a file in build artifacts.')
    build_path = dl.GetBuildDir()
    for artifact in artifacts:
      # Get the unzipped folder of the artifact. If it's not defined in
      # ARTIFACT_UNZIP_FOLDER_MAP, assume the files are unzipped to the build
      # directory directly.
      folder = artifact_info.ARTIFACT_UNZIP_FOLDER_MAP.get(artifact, '')
      artifact_path = os.path.join(build_path, folder)
      for root, _, filenames in os.walk(artifact_path):
        if file_name in set([f for f in filenames]):
          return os.path.relpath(os.path.join(root, file_name), build_path)
    raise DevServerError(
        'File `%s` can not be found in artifacts: %s' % (file_name, artifacts))

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
    dl = _get_downloader(self._static_dir, kwargs)

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
    if is_deprecated_server():
      raise DeprecatedRPCError('symbolicate_dump')

    # Ensure the symbols have been staged.
    # Try debug.tar.xz first, then debug.tgz
    for artifact in (artifact_info.SYMBOLS_ONLY, artifact_info.SYMBOLS):
      kwargs['artifacts'] = artifact
      dl = _get_downloader(self._static_dir, kwargs)

      try:
        if self.stage(**kwargs) == 'Success':
          break
      except build_artifact.ArtifactDownloadError:
        continue
    else:
      raise DevServerError(
          'Failed to stage symbols for %s' % dl.DescribeSource())

    to_return = ''
    with tempfile.NamedTemporaryFile() as local:
      while True:
        data = minidump.file.read(8192)
        if not data:
          break
        local.write(data)

      local.flush()

      symbols_directory = os.path.join(dl.GetBuildDir(), 'debug', 'breakpad')

      # The location of minidump_stackwalk is defined in chromeos-admin.
      stackwalk = subprocess.Popen(
          ['/usr/local/bin/minidump_stackwalk', local.name, symbols_directory],
          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

      to_return, error_text = stackwalk.communicate()
      if stackwalk.returncode != 0:
        raise DevServerError(
            "Can't generate stack trace: %s (rc=%d)" % (error_text,
                                                        stackwalk.returncode))

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
    if is_deprecated_server():
      raise DeprecatedRPCError('latestbuild')

    if not kwargs:
      return _PrintDocStringAsHTML(self.latestbuild)

    if 'target' not in kwargs:
      raise DevServerHTTPError(http_client.INTERNAL_SERVER_ERROR,
                               'Error: target= is required!')

    if _is_android_build_request(kwargs):
      branch = kwargs.get('branch', None)
      target = kwargs.get('target', None)
      if not target or not branch:
        raise DevServerError('Both target and branch must be specified to query'
                             ' for the latest Android build.')
      return android_build.BuildAccessor.GetLatestBuildID(target, branch)

    try:
      return common_util.GetLatestBuildVersion(
          self._static_dir, kwargs['target'],
          milestone=kwargs.get('milestone'))
    except common_util.CommonUtilError as errmsg:
      raise DevServerHTTPError(http_client.INTERNAL_SERVER_ERROR,
                               str(errmsg))

  @cherrypy.expose
  def list_suite_controls(self, **kwargs):
    """Return a list of contents of all known control files.

    Example URL:
      To List all control files' content:
      http://dev-server/list_suite_controls?suite_name=bvt&
      build=daisy_spring-release/R29-4279.0.0

    Args:
      build: The build i.e. x86-alex-release/R18-1514.0.0-a1-b1450.
      suite_name: List the control files belonging to that suite.

    Returns:
      A dictionary of all control files's path to its content for given suite.
    """
    if is_deprecated_server():
      raise DeprecatedRPCError('list_suite_controls')

    if not kwargs:
      return _PrintDocStringAsHTML(self.controlfiles)

    if 'build' not in kwargs:
      raise DevServerHTTPError(http_client.INTERNAL_SERVER_ERROR,
                               'Error: build= is required!')

    if 'suite_name' not in kwargs:
      raise DevServerHTTPError(http_client.INTERNAL_SERVER_ERROR,
                               'Error: suite_name= is required!')

    control_file_list = [
        line.rstrip() for line in common_util.GetControlFileListForSuite(
            self._static_dir, kwargs['build'],
            kwargs['suite_name']).splitlines()]

    control_file_content_dict = {}
    for control_path in control_file_list:
      control_file_content_dict[control_path] = (common_util.GetControlFile(
          self._static_dir, kwargs['build'], control_path))

    return json.dumps(control_file_content_dict)

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
    if is_deprecated_server():
      raise DeprecatedRPCError('controlfiles')

    if not kwargs:
      return _PrintDocStringAsHTML(self.controlfiles)

    if 'build' not in kwargs:
      raise DevServerHTTPError(http_client.INTERNAL_SERVER_ERROR,
                               'Error: build= is required!')

    if 'control_path' not in kwargs:
      if 'suite_name' in kwargs and kwargs['suite_name']:
        return common_util.GetControlFileListForSuite(
            self._static_dir, kwargs['build'], kwargs['suite_name'])
      else:
        return common_util.GetControlFileList(
            self._static_dir, kwargs['build'])
    else:
      return common_util.GetControlFile(
          self._static_dir, kwargs['build'], kwargs['control_path'])

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
    if is_deprecated_server():
      raise DeprecatedRPCError('xbuddy_translate')

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
      If |return_dir|, return a uri to the folder where the artifact is. E.g.,
        http://host:port/static/x86-generic-release/R26-4000.0.0/
      If |relative_path| is true, return a relative path the folder where the
      payloads are. E.g.,
        archive/x86-generic-release/R26-4000.0.0
    """
    if is_deprecated_server():
      raise DeprecatedRPCError('xbuddy')

    boolean_string = kwargs.get('return_dir')
    return_dir = xbuddy.XBuddy.ParseBoolean(boolean_string)
    boolean_string = kwargs.get('relative_path')
    relative_path = xbuddy.XBuddy.ParseBoolean(boolean_string)

    if return_dir and relative_path:
      raise DevServerHTTPError(
          http_client.INTERNAL_SERVER_ERROR,
          'Cannot specify both return_dir and relative_path')

    build_id, file_name = self._xbuddy.Get(args)

    response = None
    if return_dir:
      response = os.path.join(cherrypy.request.base, 'static', build_id)
      _Log('Directory requested, returning: %s', response)
    elif relative_path:
      response = build_id
      _Log('Relative path requested, returning: %s', response)
    else:
      # Redirect to download the payload if no kwargs are set.
      build_id = '/' + os.path.join('static', build_id, file_name)
      _Log('Payload requested, returning: %s', build_id)
      raise cherrypy.HTTPRedirect(build_id, 302)

    return response

  @cherrypy.expose
  def xbuddy_capacity(self):
    """Returns the number of images cached by xBuddy."""
    if is_deprecated_server():
      raise DeprecatedRPCError('xbuddy_capacity')

    return self._xbuddy.Capacity()

  @cherrypy.expose
  def index(self):
    """Presents a welcome message and documentation links."""
    if is_deprecated_server():
      raise DeprecatedRPCError('index')

    html_template = (
        'Welcome to the Dev Server!<br>\n'
        '<br>\n'
        'Here are the available methods, click for documentation:<br>\n'
        '<br>\n'
        '%s')

    exposed_methods = []
    for app in cherrypy.tree.apps.values():
      exposed_methods += _FindExposedMethods(
          app.root, app.script_name.lstrip('/'),
          unlisted=self._UNLISTED_METHODS)

    return html_template % '<br>\n'.join(
        ['<a href=doc/%s>%s</a>' % (name, name)
         for name in sorted(exposed_methods)])

  @cherrypy.expose
  def doc(self, *args):
    """Shows the documentation for available methods / URLs.

    Examples:
      http://myhost/doc/xbuddy
    """
    if is_deprecated_server():
      raise DeprecatedRPCError('doc')

    name = '/'.join(args)
    method = _GetExposedMethod(name)
    if not method:
      raise DevServerError("No exposed method named `%s'" % name)
    if not method.__doc__:
      raise DevServerError("No documentation for exposed method `%s'" % name)
    return '<pre>\n%s</pre>' % method.__doc__


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
                   help='do not start the server (yet clear cache)')
  parser.add_option_group(group)


def _AddProductionOptions(parser):
  group = optparse.OptionGroup(
      parser, 'Advanced Server Options', 'These options can be used to changed '
      'for advanced server behavior.')
  group.add_option('--clear_cache',
                   action='store_true', default=False,
                   help='At startup, removes all cached entries from the'
                   "devserver's cache.")
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


def MakeLogHandler(logfile):
  """Create a LogHandler instance used to log all messages."""
  hdlr_cls = handlers.TimedRotatingFileHandler
  hdlr = hdlr_cls(logfile, when=_LOG_ROTATION_TIME,
                  interval=_LOG_ROTATION_INTERVAL,
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
  parser.add_option('--infra_removal',
                    action='store_true', default=False,
                    help='If option is present, some RPCs will be disabled to '
                         'help with infra removal efforts. See '
                         'go/devserver-deprecation')
  _AddProductionOptions(parser)
  _AddTestingOptions(parser)
  (options, _) = parser.parse_args()

  # Handle options that must be set globally in cherrypy.  Do this
  # work up front, because calls to _Log() below depend on this
  # initialization.
  if options.production:
    cherrypy.config.update({'environment': 'production'})
  cherrypy.config.update({'infra_removal': options.infra_removal})
  if not options.logfile:
    cherrypy.config.update({'log.screen': True})
  else:
    cherrypy.config.update({'log.error_file': '',
                            'log.access_file': ''})
    hdlr = MakeLogHandler(options.logfile)
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

  pkgroot_dir = os.path.join(options.static_dir, 'pkgroot')
  common_util.SymlinkFile('/build', pkgroot_dir)

  _Log('Using cache directory %s' % cache_dir)
  _Log('Serving from %s' % options.static_dir)

  _xbuddy = xbuddy.XBuddy(manage_builds=options.xbuddy_manage_builds,
                          static_dir=options.static_dir)
  if options.clear_cache and options.xbuddy_manage_builds:
    _xbuddy.CleanCache()

  if options.exit:
    return

  dev_server = DevServerRoot(_xbuddy, options.static_dir)
  health_checker_app = health_checker.Root(dev_server, options.static_dir)

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

  cherrypy.tree.mount(health_checker_app, '/check_health',
                      config=health_checker.get_config())
  cherrypy.quickstart(dev_server, config=_GetConfig(options))


if __name__ == '__main__':
  main()
