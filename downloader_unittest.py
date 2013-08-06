#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for downloader module."""

import mox
import os
import shutil
import tempfile
import unittest

import build_artifact
import downloader


# pylint: disable=W0212,E1120
class DownloaderTestBase(mox.MoxTestBase):

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self._work_dir = tempfile.mkdtemp('downloader-test')
    self.board = 'x86-mario-release'
    self.build = 'R17-1413.0.0-a1-b1346'
    self.archive_url = (
        'gs://chromeos-image-archive/%s/%s' % (self.board, self.build))

  def tearDown(self):
    shutil.rmtree(self._work_dir, ignore_errors=True)

  def testSimpleDownloadOfTestSuites(self):
    """Basic test_suites test.

    Verifies that if we request the test_suites, it gets downloaded and
    the autotest tarball is attempted in the background.
    """
    downloader_instance = downloader.Downloader(self._work_dir,
                                                self.archive_url)
    self.mox.StubOutWithMock(downloader.Downloader,
                             '_DownloadArtifactsSerially')
    self.mox.StubOutWithMock(downloader.Downloader,
                             '_DownloadArtifactsInBackground')

    downloader.Downloader._DownloadArtifactsInBackground(mox.In(mox.IsA(
        build_artifact.AutotestTarballBuildArtifact)))
    downloader.Downloader._DownloadArtifactsSerially(
        [mox.IsA(build_artifact.TarballBuildArtifact)], no_wait=True)
    self.mox.ReplayAll()
    downloader_instance.Download(artifacts=['test_suites'],
                                 files=None)
    # Sanity check the timestamp file exists.
    self.assertTrue(os.path.exists(
        os.path.join(self._work_dir, self.board, self.build,
                     downloader.Downloader._TIMESTAMP_FILENAME)))
    self.mox.VerifyAll()

  def testDownloadSymbols(self):
    """Basic symbols download."""
    downloader_instance = downloader.Downloader(self._work_dir,
                                                self.archive_url)
    self.mox.StubOutWithMock(downloader.Downloader,
                             '_DownloadArtifactsSerially')
    # Should not get called but mocking so that we know it wasn't called.
    self.mox.StubOutWithMock(downloader.Downloader,
                             '_DownloadArtifactsInBackground')
    downloader.Downloader._DownloadArtifactsSerially(
        [mox.IsA(build_artifact.TarballBuildArtifact)], no_wait=True)
    self.mox.ReplayAll()
    downloader_instance.Download(artifacts=['symbols'],
                                 files=None)
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
