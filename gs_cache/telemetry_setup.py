# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A class that sets up the environment for telemetry testing."""

from __future__ import print_function

import contextlib
import errno
import fcntl
import os
import shutil
import subprocess
import tempfile

import requests

import cherrypy  # pylint: disable=import-error

import constants

from chromite.lib import cros_logging as logging


# Define module logger.
_logger = logging.getLogger(__file__)

# Define all GS Cache related constants.
GS_CACHE_HOSTNAME = '127.0.0.1'
GS_CACHE_PORT = '8888'
GS_CACHE_EXRTACT_RPC = 'extract'
GS_CACHE_BASE_URL = ('http://%s:%s/%s' %
                     (GS_CACHE_HOSTNAME, GS_CACHE_PORT, GS_CACHE_EXRTACT_RPC))
_TIMESTAMP_FILE = 'staged.timestamp'


def _log(*args, **kwargs):
  """A wrapper function of logging.debug/info, etc."""
  level = kwargs.pop('level', logging.DEBUG)
  _logger.log(level, extra=cherrypy.request.headers, *args, **kwargs)


def _touch_timestamp(dir_name):
  """Timestamp the directory to allow other jobs to clean it."""
  file_name = os.path.join(dir_name, _TIMESTAMP_FILE)
  # Easiest python version of |touch file_name|.
  with open(file_name, 'a'):
    os.utime(file_name, None)


def _GetBucketAndBuild(archive_url):
  """Gets the build name from the archive_url.

  Args:
    archive_url: The archive_url is typically in the format
        gs://<gs_bucket>/<build_name>. Deduce the bucket and build name from
        this URL by splitting at the appropriate '/'.

  Returns:
    Name of the GS bucket as a string.
    Name of the build as a string.
  """
  clean_url = archive_url.strip('gs://')
  parts = clean_url.split('/')
  return parts[0], '/'.join(parts[1:])


@contextlib.contextmanager
def lock_dir(dir_name):
  """Lock a directory exclusively by placing a file lock in it.

  Args:
    dir_name: the directory name to be locked.
  """
  lock_file = os.path.join(dir_name, '.lock')
  with open(lock_file, 'w+') as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    try:
      yield
    finally:
      fcntl.flock(f, fcntl.LOCK_UN)


class TelemetrySetupError(Exception):
  """Exception class used by this module."""


class TelemetrySetup(object):
  """Class that sets up the environment for telemetry testing."""

  # Relevant directory paths.
  _BASE_DIR_PATH = '/home/chromeos-test/images'
  _PARTIAL_DEPENDENCY_DIR_PATH = 'autotest/packages'

  # Relevant directory names.
  _TELEMETRY_SRC_DIR_NAME = 'telemetry_src'
  _TEST_SRC_DIR_NAME = 'test_src'
  _SRC_DIR_NAME = 'src'

  # Names of the telemetry dependency tarballs.
  _DEPENDENCIES = [
      'dep-telemetry_dep.tar.bz2',
      'dep-page_cycler_dep.tar.bz2',
      'dep-chrome_test.tar.bz2',
      'dep-perf_data_dep.tar.bz2',
  ]

  def __init__(self, archive_url):
    """Initializes the TelemetrySetup class.

    Args:
      archive_url: The URL of the archive supplied through the /setup_telemetry
          request. It is typically in the format gs://<gs_bucket>/<build_name>
    """
    self._bucket, self._build = _GetBucketAndBuild(archive_url)
    self._build_dir = os.path.join(self._BASE_DIR_PATH, self._build)
    self._temp_dir_path = tempfile.mkdtemp(prefix='gsc-telemetry')
    self._tlm_src_dir_path = os.path.join(self._build_dir,
                                          self._TELEMETRY_SRC_DIR_NAME)

  def __enter__(self):
    """Called while entering context manager; does nothing."""
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    """Called while exiting context manager; cleans up temp dirs."""
    try:
      shutil.rmtree(self._temp_dir_path)
    except Exception as e:
      _log('Something went wrong. Could not delete %s due to exception: %s',
           self._temp_dir_path, e, level=logging.WARNING)

  def Setup(self):
    """Sets up the environment for telemetry testing.

    This method downloads the telemetry dependency tarballs and extracts them
    into a 'src' directory.

    Returns:
      Path to the src directry where the telemetry dependencies have been
          downloaded and extracted.
    """
    src_folder = os.path.join(self._tlm_src_dir_path, self._SRC_DIR_NAME)
    test_src = os.path.join(self._tlm_src_dir_path, self._TEST_SRC_DIR_NAME)

    self._MkDirP(self._tlm_src_dir_path)
    _touch_timestamp(self._build_dir)
    with lock_dir(self._tlm_src_dir_path):
      if not os.path.exists(src_folder):

        # Download the required dependency tarballs.
        for dep in self._DEPENDENCIES:
          dep_path = self._DownloadFilesFromTar(dep, self._temp_dir_path)
          if os.path.exists(dep_path):
            self._ExtractTarball(dep_path, self._tlm_src_dir_path)

        # By default all the tarballs extract to test_src but some parts of
        # the telemetry code specifically hardcoded to exist inside of 'src'.
        try:
          shutil.move(test_src, src_folder)
        except shutil.Error:
          raise TelemetrySetupError(
              'Failure in telemetry setup for build %s. Appears that the '
              'test_src to src move failed.' % self._build)

    return src_folder

  def _DownloadFilesFromTar(self, filename, dest_path):
    """Downloads the given tar.bz2 file.

    The given tar.bz2 file is downloaded by calling the 'extract' RPC of
    gs_archive_server.

    Args:
      filename: Name of the tar.bz2 file to be downloaded.
      dest_path: Full path to the directory where it should be downloaded.

    Returns:
      Full path to the downloaded file.

    Raises:
      TelemetrySetupError when the download cannot be completed for any reason.
    """
    dep_path = os.path.join(dest_path, filename)
    params = 'file=%s/%s' % (self._PARTIAL_DEPENDENCY_DIR_PATH, filename)
    partial_url = ('%s/%s/%s/autotest_packages.tar' %
                   (GS_CACHE_BASE_URL, self._bucket, self._build))
    url = '%s?%s' % (partial_url, params)
    resp = requests.get(url)
    try:
      resp.raise_for_status()
      with open(dep_path, 'wb') as f:
        for content in resp.iter_content(constants.READ_BUFFER_SIZE_BYTES):
          f.write(content)
    except Exception as e:
      if (isinstance(e, requests.exceptions.HTTPError)
          and resp.status_code == 404):
        _log('The request %s returned a 404 Not Found status. This dependency '
             'could be new and therefore does not exist in this specific '
             'tarball. Hence, squashing the exception and proceeding.',
             url, level=logging.ERROR)
      else:
        raise TelemetrySetupError('An error occurred while trying to complete '
                                  'the extract request %s: %s' % (url, str(e)))
    return dep_path

  def _ExtractTarball(self, tarball_path, dest_path):
    """Extracts the given tarball into the destination directory.

    Args:
      tarball_path: Full path to the tarball to be extracted.
      dest_path: Full path to the directory where the tarball should be
          extracted.

    Raises:
      TelemetrySetupError if the method is unable to extract the tarball for
          any reason.
    """
    cmd = ['tar', 'xf', tarball_path, '--directory', dest_path]
    try:
      proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
      proc.communicate()
    except Exception as e:
      shutil.rmtree(dest_path)
      raise TelemetrySetupError(
          'An exception occurred while trying to untar %s into %s: %s' %
          (tarball_path, dest_path, str(e)))

  def _MkDirP(self, path):
    """Recursively creates the given directory.

    Args:
      path: Full path to the directory that needs to the created.

    Raises:
      TelemetrySetupError is the method is unable to create directories for any
          reason except OSError EEXIST which indicates that the directory
          already exists.
    """
    try:
      os.makedirs(path)
    except Exception as e:
      if not isinstance(e, OSError) or e.errno != errno.EEXIST:
        raise TelemetrySetupError(
            'Could not create directory %s due to %s.' % (path, str(e)))
