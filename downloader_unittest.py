#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for devserver_util module."""

import mox
import os
import shutil
import tempfile
import unittest

import artifact_download
import devserver
import devserver_util
import downloader


# Fake Dev Server Layout:
TEST_LAYOUT = {
    'test-board-1': ['R17-1413.0.0-a1-b1346', 'R17-18.0.0-a1-b1346'],
    'test-board-2': ['R16-2241.0.0-a0-b2', 'R17-2.0.0-a1-b1346'],
    'test-board-3': []
}


class DownloaderTest(mox.MoxTestBase):

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self._work_dir = tempfile.mkdtemp('downloader-test')
    self.build = 'R17-1413.0.0-a1-b1346'
    self.archive_url_prefix = (
        'gs://chromeos-image-archive/x86-mario-release/' + self.build)

  def tearDown(self):
    if os.path.exists(self._work_dir):
      shutil.rmtree(self._work_dir)

  def _CommonDownloaderSetup(self):
    """Common code to downloader tests.

    Sets up artifacts and sets up expectations for synchronous artifacts to
    be downloaded first.

    Returns the artifacts to use in the test.
    """
    board = 'x86-mario-release'
    self.mox.StubOutWithMock(devserver_util, 'AcquireLock')
    self.mox.StubOutWithMock(devserver_util, 'GatherArtifactDownloads')
    self.mox.StubOutWithMock(devserver_util, 'ReleaseLock')
    self.mox.StubOutWithMock(tempfile, 'mkdtemp')

    artifacts = []

    for index in range(5):
      artifact = self.mox.CreateMock(artifact_download.DownloadableArtifact)
      # Make every other artifact synchronous.
      if index % 2 == 0:
        artifact.Synchronous = lambda: True
      else:
        artifact.Synchronous = lambda: False

      artifacts.append(artifact)

    devserver_util.AcquireLock(
        static_dir=self._work_dir,
        tag='/'.join([board, self.build])).AndReturn(self._work_dir)

    tempfile.mkdtemp(suffix=mox.IgnoreArg()).AndReturn(self._work_dir)
    devserver_util.GatherArtifactDownloads(
        self._work_dir, self.archive_url_prefix, self.build,
        self._work_dir).AndReturn(artifacts)

    for index, artifact in enumerate(artifacts):
      if index % 2 == 0:
        artifact.Download()
        artifact.Stage()

    return artifacts

  def testDownloaderSerially(self):
    """Runs through the standard downloader workflow with no backgrounding."""
    artifacts = self._CommonDownloaderSetup()

    # Downloads non-synchronous artifacts second.
    for index, artifact in enumerate(artifacts):
      if index % 2 != 0:
        artifact.Download()
        artifact.Stage()

    self.mox.ReplayAll()
    self.assertEqual(downloader.Downloader(self._work_dir).Download(
        self.archive_url_prefix, background=False), 'Success')
    self.mox.VerifyAll()

  def testDownloaderInBackground(self):
    """Runs through the standard downloader workflow with backgrounding."""
    artifacts = self._CommonDownloaderSetup()

    # Downloads non-synchronous artifacts second.
    for index, artifact in enumerate(artifacts):
      if index % 2 != 0:
        artifact.Download()
        artifact.Stage()

    self.mox.ReplayAll()
    d = downloader.Downloader(self._work_dir)
    d.Download(self.archive_url_prefix, background=True)
    self.assertEqual(d.GetStatusOfBackgroundDownloads(), 'Success')
    self.mox.VerifyAll()

  def testInteractionWithDevserver(self):
    artifacts = self._CommonDownloaderSetup()
    class FakeUpdater():
      static_dir = self._work_dir

    devserver.updater = FakeUpdater()

    # Downloads non-synchronous artifacts second.
    for index, artifact in enumerate(artifacts):
      if index % 2 != 0:
        artifact.Download()
        artifact.Stage()

    self.mox.ReplayAll()
    dev = devserver.DevServerRoot()
    status = dev.download(archive_url=self.archive_url_prefix)
    self.assertTrue(status, 'Success')
    status = dev.wait_for_status(archive_url=self.archive_url_prefix)
    self.assertTrue(status, 'Success')
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
