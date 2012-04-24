# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing classes that wrap artifact downloads."""

import cherrypy
import os
import shutil
import subprocess

import gsutil_util


# Names of artifacts we care about.
DEBUG_SYMBOLS = 'debug.tgz'
STATEFUL_UPDATE = 'stateful.tgz'
TEST_IMAGE = 'chromiumos_test_image.bin'
ROOT_UPDATE = 'update.gz'
AUTOTEST_PACKAGE = 'autotest.tar.bz2'
TEST_SUITES_PACKAGE = 'test_suites.tar.bz2'


class ArtifactDownloadError(Exception):
  """Error used to signify an issue processing an artifact."""
  pass


class DownloadableArtifact(object):
  """Wrapper around an artifact to download from gsutil.

  The purpose of this class is to download objects from Google Storage
  and install them to a local directory. There are two main functions, one to
  download/prepare the artifacts in to a temporary staging area and the second
  to stage it into its final destination.
  """
  def __init__(self, gs_path, tmp_staging_dir, install_path, synchronous=False):
    """Args:
      gs_path: Path to artifact in google storage.
      tmp_staging_dir: Temporary working directory maintained by caller.
      install_path: Final destination of artifact.
      synchronous: If True, artifact must be downloaded in the foreground.
    """
    self._gs_path = gs_path
    self._tmp_staging_dir = tmp_staging_dir
    self._tmp_stage_path = os.path.join(tmp_staging_dir,
                                        os.path.basename(self._gs_path))
    self._synchronous = synchronous
    self._install_path = install_path

    if not os.path.isdir(self._tmp_staging_dir):
      os.makedirs(self._tmp_staging_dir)

    if not os.path.isdir(os.path.dirname(self._install_path)):
      os.makedirs(os.path.dirname(self._install_path))

  def Download(self):
    """Stages the artifact from google storage to a local staging directory."""
    gsutil_util.DownloadFromGS(self._gs_path, self._tmp_stage_path)

  def Synchronous(self):
    """Returns False if this artifact can be downloaded in the background."""
    return self._synchronous

  def Stage(self):
    """Moves the artifact from the tmp staging directory to the final path."""
    shutil.move(self._tmp_stage_path, self._install_path)

  def __str__(self):
    """String representation for the download."""
    return '->'.join([self._gs_path, self._tmp_staging_dir, self._install_path])


class AUTestPayload(DownloadableArtifact):
  """Wrapper for AUTest delta payloads which need additional setup."""
  def Stage(self):
    super(AUTestPayload, self).Stage()

    payload_dir = os.path.dirname(self._install_path)
    # Setup necessary symlinks for updating.
    os.symlink(os.path.join(os.pardir, os.pardir, TEST_IMAGE),
               os.path.join(payload_dir, TEST_IMAGE))
    os.symlink(os.path.join(os.pardir, os.pardir, STATEFUL_UPDATE),
               os.path.join(payload_dir, STATEFUL_UPDATE))


class Tarball(DownloadableArtifact):
  """Wrapper around an artifact to download from gsutil which is a tarball."""

  def _ExtractTarball(self, exclude=None):
    """Extracts the tarball into the install_path with optional exclude path."""
    exclude_str = '--exclude=%s' % exclude if exclude else ''
    cmd = 'tar xf %s %s --use-compress-prog=pbzip2 --directory=%s' % (
        self._tmp_stage_path, exclude_str, self._install_path)
    msg = 'An error occurred when attempting to untar %s' % self._tmp_stage_path
    try:
      subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError, e:
      raise ArtifactDownloadError('%s %s' % (msg, e))

  def Stage(self):
    """Changes directory into the install path and untars the tarball."""
    if not os.path.isdir(self._install_path):
      os.makedirs(self._install_path)

    self._ExtractTarball()


class AutotestTarball(Tarball):
  """Wrapper around the autotest tarball to download from gsutil."""

  def Stage(self):
    """Untars the autotest tarball into the install path excluding test suites.
    """
    if not os.path.isdir(self._install_path):
      os.makedirs(self._install_path)

    self._ExtractTarball(exclude='autotest/test_suites')
    autotest_dir = os.path.join(self._install_path, 'autotest')
    autotest_pkgs_dir = os.path.join(autotest_dir, 'packages')
    if not os.path.exists(autotest_pkgs_dir):
      os.makedirs(autotest_pkgs_dir)

    if not os.path.exists(os.path.join(autotest_pkgs_dir, 'packages.checksum')):
      cmd = 'autotest/utils/packager.py upload --repository=%s --all' % (
          autotest_pkgs_dir)
      msg = 'Failed to create autotest packages!'
      try:
        subprocess.check_call(cmd, cwd=self._tmp_staging_dir,
                              shell=True)
      except subprocess.CalledProcessError, e:
        raise ArtifactDownloadError('%s %s' % (msg, e))
    else:
      cherrypy.log('Using pre-generated packages from autotest',
                   'DEVSERVER_UTIL')

    # TODO(scottz): Remove after we have moved away from the old test_scheduler
    # code.
    cmd = 'cp %s/* %s' % (autotest_pkgs_dir, autotest_dir)
    subprocess.check_call(cmd, shell=True)


class DebugTarball(Tarball):
  """Wrapper around the debug symbols tarball to download from gsutil."""

  def _ExtractTarball(self):
    """Extracts debug/breakpad from the tarball into the install_path."""
    cmd = 'tar xzf %s --directory=%s debug/breakpad' % (
        self._tmp_stage_path, self._install_path)
    msg = 'An error occurred when attempting to untar %s' % self._tmp_stage_path
    try:
      subprocess.check_call(cmd, shell=True)
    except subprocess.CalledProcessError, e:
      raise ArtifactDownloadError('%s %s' % (msg, e))
