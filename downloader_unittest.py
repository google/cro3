#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for downloader module."""

from __future__ import print_function

import mox
import os
import shutil
import tempfile
import unittest

import build_artifact
import downloader


# pylint: disable=W0212,E1120
class DownloaderTestBase(mox.MoxTestBase):
  """Downloader Unittests."""

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self._work_dir = tempfile.mkdtemp('downloader-test')
    self.board = 'x86-mario-release'
    self.build = 'R17-1413.0.0-a1-b1346'
    self.archive_url = (
        'gs://chromeos-image-archive/%s/%s' % (self.board, self.build))
    self.local_path = ('/local/path/x86-mario-release/R17-1413.0.0-a1-b1346')

  def tearDown(self):
    shutil.rmtree(self._work_dir, ignore_errors=True)

  def _SimpleDownloadOfTestSuites(self, downloader_instance):
    """Helper to verify test_suites are downloaded correctly.

    Args:
      downloader_instance: Downloader object to test with.
    """
    factory = build_artifact.ChromeOSArtifactFactory(
        downloader_instance.GetBuildDir(), ['test_suites'],
        None, downloader_instance.GetBuild())
    self.mox.StubOutWithMock(downloader.Downloader,
                             '_DownloadArtifactsSerially')
    self.mox.StubOutWithMock(downloader.Downloader,
                             '_DownloadArtifactsInBackground')

    downloader.Downloader._DownloadArtifactsInBackground(mox.In(mox.IsA(
        build_artifact.AutotestTarball)))
    downloader.Downloader._DownloadArtifactsSerially(
        [mox.IsA(build_artifact.BundledArtifact)], no_wait=True)
    self.mox.ReplayAll()
    downloader_instance.Download(factory)
    # Sanity check the timestamp file exists.
    self.assertTrue(os.path.exists(
        os.path.join(self._work_dir, self.board, self.build,
                     downloader.Downloader._TIMESTAMP_FILENAME)))
    self.mox.VerifyAll()

  def testSimpleDownloadOfTestSuitesFromGS(self):
    """Basic test_suites test.

    Verifies that if we request the test_suites from Google Storage, it gets
    downloaded and the autotest tarball is attempted in the background.
    """
    self._SimpleDownloadOfTestSuites(
        downloader.GoogleStorageDownloader(
            self._work_dir, self.archive_url,
            downloader.GoogleStorageDownloader.GetBuildIdFromArchiveURL(
                self.archive_url)))

  def testSimpleDownloadOfTestSuitesFromLocal(self):
    """Basic test_suites test.

    Verifies that if we request the test_suites from a local path, it gets
    downloaded and the autotest tarball is attempted in the background.
    """
    self._SimpleDownloadOfTestSuites(
        downloader.LocalDownloader(self._work_dir, self.local_path))

  def _DownloadSymbolsHelper(self, downloader_instance):
    """Basic symbols download."""
    factory = build_artifact.ChromeOSArtifactFactory(
        downloader_instance.GetBuildDir(), ['symbols'],
        None, downloader_instance.GetBuild())

    self.mox.StubOutWithMock(downloader.Downloader,
                             '_DownloadArtifactsSerially')
    # Should not get called but mocking so that we know it wasn't called.
    self.mox.StubOutWithMock(downloader.Downloader,
                             '_DownloadArtifactsInBackground')
    downloader.Downloader._DownloadArtifactsSerially(
        [mox.IsA(build_artifact.BundledArtifact)], no_wait=True)
    self.mox.ReplayAll()
    downloader_instance.Download(factory)
    self.mox.VerifyAll()

  def testDownloadSymbolsFromGS(self):
    """Basic symbols download from Google Storage."""
    self._DownloadSymbolsHelper(
        downloader.GoogleStorageDownloader(
            self._work_dir, self.archive_url,
            downloader.GoogleStorageDownloader.GetBuildIdFromArchiveURL(
                self.archive_url)))

  def testDownloadSymbolsFromLocal(self):
    """Basic symbols download from a Local Path."""
    self._DownloadSymbolsHelper(
        downloader.LocalDownloader(self._work_dir, self.local_path))


class AndroidDownloaderTestBase(mox.MoxTestBase):
  """Android Downloader Unittests."""

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self._work_dir = tempfile.mkdtemp('downloader-test')
    self.branch = 'release'
    self.target = 'shamu-userdebug'
    self.build_id = '123456'

  def tearDown(self):
    shutil.rmtree(self._work_dir, ignore_errors=True)

  def testDownloadFromAndroidBuildServer(self):
    """Basic test to check download from Android's build server works."""
    downloader_instance = downloader.AndroidBuildDownloader(
        self._work_dir, self.branch, self.build_id, self.target)
    factory = build_artifact.AndroidArtifactFactory(
        downloader_instance.GetBuildDir(), ['fastboot'],
        None, downloader_instance.GetBuild())
    self.mox.StubOutWithMock(downloader.Downloader,
                             '_DownloadArtifactsSerially')
    self.mox.StubOutWithMock(downloader.Downloader,
                             '_DownloadArtifactsInBackground')

    downloader.Downloader._DownloadArtifactsSerially(
        [mox.IsA(build_artifact.Artifact)], no_wait=True)
    self.mox.ReplayAll()
    downloader_instance.Download(factory)
    # Sanity check the timestamp file exists.
    self.assertTrue(os.path.exists(
        os.path.join(self._work_dir, self.branch, self.target, self.build_id,
                     downloader.Downloader._TIMESTAMP_FILENAME)))
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
