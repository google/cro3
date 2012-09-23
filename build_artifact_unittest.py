#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for build_artifact module.

These unit tests take tarball from google storage locations to fully test
the artifact download process. Please make sure to set up your boto file and
run these unittests from within the chroot.  The tools are self-explanatory.
"""

import os
import shutil
import subprocess
import tempfile
import unittest

import mox

import build_artifact


_TEST_GOLO_ARCHIVE = (
    'gs://chromeos-image-archive/x86-alex-release/R19-2003.0.0-a1-b1819')
_TEST_SUITES_TAR = '/'.join([_TEST_GOLO_ARCHIVE,
                             build_artifact.TEST_SUITES_PACKAGE])
_TEST_TEMP_ARCHIVE = (
    'gs://chromeos-image-archive/trybot-lumpy-paladin/R22-2531.0.0-a1-b145')
_AUTOTEST_TAR = '/'.join([_TEST_TEMP_ARCHIVE,
                          build_artifact.AUTOTEST_PACKAGE])


class BuildArtifactTest(mox.MoxTestBase):

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.work_dir = tempfile.mkdtemp('build_artifact')

  def tearDown(self):
    shutil.rmtree(self.work_dir)

  def testDownloadAndStage(self):
    """Downloads a real tarball from GSUtil."""
    artifact = build_artifact.BuildArtifact(
        _TEST_SUITES_TAR, os.path.join(self.work_dir, 'stage'),
        os.path.join(self.work_dir, 'install', 'file'), True)
    artifact.Download()
    artifact.Stage()
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, 'install', 'file')))

  def testDownloadAndStageTarball(self):
    """Downloads a real tarball and untars it."""
    artifact = build_artifact.TarballBuildArtifact(
        _TEST_SUITES_TAR, os.path.join(self.work_dir, 'stage'),
        os.path.join(self.work_dir, 'install'), True)
    artifact.Download()
    artifact.Stage()
    self.assertTrue(os.path.isdir(os.path.join(
        self.work_dir, 'install', 'autotest', 'test_suites')))


  def testDownloadAndStageAutotest(self):
    """Downloads a real autotest tarball for test."""
    artifact = build_artifact.AutotestTarballBuildArtifact(
        _AUTOTEST_TAR, os.path.join(self.work_dir, 'stage'),
        os.path.join(self.work_dir, 'install'), True)
    artifact.Download()
    self.mox.StubOutWithMock(build_artifact.AutotestTarballBuildArtifact,
                             '_ExtractTarball')
    self.mox.StubOutWithMock(subprocess, 'check_call')
    build_artifact.AutotestTarballBuildArtifact._ExtractTarball(
        exclude='autotest/test_suites')
    subprocess.check_call(mox.StrContains('autotest/utils/packager.py'),
                          cwd=os.path.join(self.work_dir, 'stage'), shell=True)
    subprocess.check_call('cp %s %s' % (
        os.path.join(self.work_dir, 'install', 'autotest', 'packages/*'),
        os.path.join(self.work_dir, 'install', 'autotest')), shell=True)
    self.mox.ReplayAll()
    artifact.Stage()
    self.mox.VerifyAll()
    self.assertTrue(os.path.isdir(os.path.join(self.work_dir, 'install',
                                               'autotest', 'packages')))

  def testAUTestPayloadBuildArtifact(self):
    """Downloads a real tarball and treats it like an AU payload."""
    open(os.path.join(self.work_dir, build_artifact.STATEFUL_UPDATE),
         'a').close()
    open(os.path.join(self.work_dir, build_artifact.TEST_IMAGE),
         'a').close()

    artifact = build_artifact.AUTestPayloadBuildArtifact(
        _TEST_SUITES_TAR, os.path.join(self.work_dir, 'stage'),
        os.path.join(self.work_dir, 'install', 'payload', 'payload.gz'), True)
    artifact.Download()
    artifact.Stage()
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, 'install', 'payload', 'payload.gz')))
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, 'install', 'payload',
        build_artifact.STATEFUL_UPDATE)))
    self.assertTrue(os.path.exists(os.path.join(
        self.work_dir, 'install', 'payload', build_artifact.TEST_IMAGE)))


if __name__ == '__main__':
  unittest.main()
