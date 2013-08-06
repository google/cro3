#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for build_artifact module.

These unit tests take tarball from google storage locations to fully test
the artifact download process. Please make sure to set up your boto file.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

import mox

import build_artifact


_VERSION = 'R26-3646.0.0-rc1'
_TEST_GOLO_ARCHIVE = (
    'gs://chromeos-image-archive/x86-generic-chromium-pfq/R26-3646.0.0-rc1')

# Different as the above does not have deltas (for smaller artifacts).
_DELTA_VERSION = 'R26-3645.0.0'
_TEST_GOLO_FOR_DELTAS = (
    'gs://chromeos-image-archive/x86-mario-release/R26-3645.0.0')


# pylint: disable=W0212
class BuildArtifactTest(mox.MoxTestBase):

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.work_dir = tempfile.mkdtemp('build_artifact_unittest')

  def tearDown(self):
    shutil.rmtree(self.work_dir)

  def testProcessBuildArtifact(self):
    """Processes a real tarball from GSUtil and stages it."""
    artifact = build_artifact.BuildArtifact(
        self.work_dir,
        _TEST_GOLO_ARCHIVE, build_artifact.TEST_SUITES_FILE, _VERSION)
    artifact.Process(False)
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, build_artifact.TEST_SUITES_FILE)))

  def testProcessTarball(self):
    """Downloads a real tarball and untars it."""
    artifact = build_artifact.TarballBuildArtifact(
        self.work_dir, _TEST_GOLO_ARCHIVE, build_artifact.TEST_SUITES_FILE,
        _VERSION)
    artifact.Process(False)
    self.assertTrue(os.path.isdir(os.path.join(
        self.work_dir, 'autotest', 'test_suites')))

  def testProcessTarballWithFile(self):
    """Downloads a real tarball and only untars one file from it."""
    file_to_download = 'autotest/test_suites/control.au'
    artifact = build_artifact.TarballBuildArtifact(
        self.work_dir, _TEST_GOLO_ARCHIVE, build_artifact.TEST_SUITES_FILE,
        _VERSION, [file_to_download])
    artifact.Process(False)
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, file_to_download)))

  def testDownloadAutotest(self):
    """Downloads a real autotest tarball for test."""
    self.mox.StubOutWithMock(build_artifact.AutotestTarballBuildArtifact,
                             '_Extract')
    artifact = build_artifact.AutotestTarballBuildArtifact(
        self.work_dir, _TEST_GOLO_ARCHIVE, build_artifact.AUTOTEST_FILE,
        _VERSION, None, ['autotest/test_suites'])

    install_dir = self.work_dir
    artifact.staging_dir = install_dir
    artifact._Download()
    self.mox.StubOutWithMock(subprocess, 'check_call')
    artifact._Extract()
    subprocess.check_call(mox.In('autotest/utils/packager.py'), cwd=install_dir)
    self.mox.ReplayAll()
    artifact._Setup()
    self.mox.VerifyAll()
    self.assertTrue(os.path.isdir(
        os.path.join(self.work_dir, 'autotest', 'packages')))

  def testAUTestPayloadBuildArtifact(self):
    """Downloads a real tarball and treats it like an AU payload."""
    artifact = build_artifact.AUTestPayloadBuildArtifact(
        self.work_dir, _TEST_GOLO_ARCHIVE, build_artifact.TEST_SUITES_FILE,
        _VERSION)
    artifact.Process(False)
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, 'update.gz')))

  def testDeltaPayloadsArtifact(self):
    """Downloads delta paylaods from test bucket."""
    artifact = build_artifact.DeltaPayloadsArtifact(
        self.work_dir, _TEST_GOLO_FOR_DELTAS, '.*_delta_.*', _DELTA_VERSION)
    artifact.Process(False)
    nton_dir = os.path.join(self.work_dir, 'au', '%s_nton' % _DELTA_VERSION)
    mton_dir = os.path.join(self.work_dir, 'au', '%s_mton' % _DELTA_VERSION)
    self.assertTrue(os.path.exists(os.path.join(nton_dir, 'update.gz')))
    self.assertTrue(os.path.exists(os.path.join(mton_dir, 'update.gz')))

  def testImageUnzip(self):
    """Downloads and stages a zip file and extracts a test image."""
    artifact = build_artifact.ZipfileBuildArtifact(
        self.work_dir, _TEST_GOLO_ARCHIVE, build_artifact.IMAGE_FILE,
        _VERSION, ['chromiumos_test_image.bin'])
    artifact.Process(False)
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, 'chromiumos_test_image.bin')))

  def testImageUnzipWithExcludes(self):
    """Downloads and stages a zip file while excluding all large files."""
    artifact = build_artifact.ZipfileBuildArtifact(
        self.work_dir, _TEST_GOLO_ARCHIVE, build_artifact.IMAGE_FILE,
        _VERSION, None, ['*.bin'])
    artifact.Process(False)
    self.assertFalse(os.path.exists(os.path.join(
        self.work_dir, 'chromiumos_test_image.bin')))

  def testArtifactFactory(self):
    """Tests that BuildArtifact logic works for both named and file artifacts.
    """
    name_artifact = 'test_suites' # This file is in every real GS dir.
    file_artifact = 'metadata.json' # This file is in every real GS dir.
    factory = build_artifact.ArtifactFactory(self.work_dir, _TEST_GOLO_ARCHIVE,
                                             [name_artifact], [file_artifact],
                                             _VERSION)
    artifacts = factory.RequiredArtifacts()
    self.assertEqual(len(artifacts), 2)
    artifacts[0].Process(False)
    artifacts[1].Process(False)
    # Test suites directory exists.
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, 'autotest', 'test_suites')))
    # File artifact was staged.
    self.assertTrue(os.path.exists(os.path.join(self.work_dir,
                                                file_artifact)))


if __name__ == '__main__':
  unittest.main()
