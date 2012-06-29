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

import downloadable_artifact
import devserver
import devserver_util
import downloader


# Fake Dev Server Layout:
TEST_LAYOUT = {
    'test-board-1': ['R17-1413.0.0-a1-b1346', 'R17-18.0.0-a1-b1346'],
    'test-board-2': ['R16-2241.0.0-a0-b2', 'R17-2.0.0-a1-b1346'],
    'test-board-3': []
}


class DownloaderTestBase(mox.MoxTestBase):

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self._work_dir = tempfile.mkdtemp('downloader-test')
    self.build = 'R17-1413.0.0-a1-b1346'
    self.archive_url_prefix = (
        'gs://chromeos-image-archive/x86-mario-release/' + self.build)

  def tearDown(self):
    if os.path.exists(self._work_dir):
      shutil.rmtree(self._work_dir)

  def _CommonDownloaderSetup(self, ignore_background=False):
    """Common code to downloader tests.

    Mocks out key devserver_util module methods, creates mock artifacts
    and sets appropriate expectations.

    @ignore_background Indicate that background artifacts should be ignored.

    @return iterable of artifact objects with appropriate expectations.
    """
    board = 'x86-mario-release'
    self.mox.StubOutWithMock(devserver_util, 'AcquireLock')
    self.mox.StubOutWithMock(devserver_util, 'GatherArtifactDownloads')
    self.mox.StubOutWithMock(devserver_util, 'ReleaseLock')
    self.mox.StubOutWithMock(tempfile, 'mkdtemp')

    devserver_util.AcquireLock(
        static_dir=self._work_dir,
        tag=self._ClassUnderTest().GenerateLockTag(board, self.build)
        ).AndReturn(self._work_dir)

    tempfile.mkdtemp(suffix=mox.IgnoreArg()).AndReturn(self._work_dir)
    return self._GenerateArtifacts(ignore_background)

  def _CreateArtifactDownloader(self, artifacts):
    """Create and return a Downloader of the appropriate type.

    The returned downloader will expect to download and stage the
    DownloadableArtifacts listed in [artifacts].

    @param artifacts: iterable of DownloadableArtifacts.
    @return instance of downloader.Downloader or subclass.
    """
    raise NotImplementedError()

  def _ClassUnderTest(self):
    """Return class object of the type being tested.

    @return downloader.Downloader class object, or subclass.
    """
    raise NotImplementedError()

  def _GenerateArtifacts(self, ignore_background):
    """Instantiate artifact mocks and set expectations on them.

    @ignore_background Indicate that background artifacts should be ignored.
      This gets passed by CommonDownloaderSetup.

    @return iterable of artifact objects with appropriate expectations.
    """
    raise NotImplementedError()


class DownloaderTest(DownloaderTestBase):
  """Unit tests for downloader.Downloader.

  setUp() and tearDown() inherited from DownloaderTestBase.
  """

  def _CreateArtifactDownloader(self, artifacts):
    d = downloader.Downloader(self._work_dir)
    self.mox.StubOutWithMock(d, 'GatherArtifactDownloads')
    d.GatherArtifactDownloads(
        self._work_dir, self.archive_url_prefix, self.build,
        self._work_dir).AndReturn(artifacts)
    return d

  def _ClassUnderTest(self):
    return downloader.Downloader

  def _GenerateArtifacts(self, ignore_background):
    """Instantiate artifact mocks and set expectations on them.

    Sets up artifacts and sets up expectations for synchronous artifacts to
    be downloaded first.

    @ignore_background If True, doesn't use mocks for download/stage methods.

    @return iterable of artifact objects with appropriate expectations.
    """
    artifacts = []
    for index in range(5):
      artifact = self.mox.CreateMock(downloadable_artifact.DownloadableArtifact)
      # Make every other artifact synchronous.
      if index % 2 == 0:
        artifact.Synchronous = lambda: True
        artifact.Download()
        artifact.Stage()
      else:
        artifact.Synchronous = lambda: False
        if ignore_background:
          artifact.Download = lambda: None
          artifact.Stage = lambda: None

      artifacts.append(artifact)

    return artifacts

  def testDownloaderSerially(self):
    """Runs through the standard downloader workflow with no backgrounding."""
    artifacts = self._CommonDownloaderSetup()

    # Downloads non-synchronous artifacts second.
    for index, artifact in enumerate(artifacts):
      if index % 2 != 0:
        artifact.Download()
        artifact.Stage()

    d = self._CreateArtifactDownloader(artifacts)
    self.mox.ReplayAll()
    self.assertEqual(d.Download(self.archive_url_prefix, background=False),
                     'Success')
    self.mox.VerifyAll()

  def testDownloaderInBackground(self):
    """Runs through the standard downloader workflow with backgrounding."""
    artifacts = self._CommonDownloaderSetup(ignore_background=True)
    d = self._CreateArtifactDownloader(artifacts)
    self.mox.ReplayAll()
    d.Download(self.archive_url_prefix, background=True)
    self.assertEqual(d.GetStatusOfBackgroundDownloads(), 'Success')
    self.mox.VerifyAll()

  def testInteractionWithDevserver(self):
    """Tests interaction between the downloader and devserver methods."""
    artifacts = self._CommonDownloaderSetup(ignore_background=True)
    devserver_util.GatherArtifactDownloads(
        self._work_dir, self.archive_url_prefix, self.build,
        self._work_dir).AndReturn(artifacts)

    class FakeUpdater():
      static_dir = self._work_dir

    devserver.updater = FakeUpdater()

    self.mox.ReplayAll()
    dev = devserver.DevServerRoot()
    status = dev.download(archive_url=self.archive_url_prefix)
    self.assertTrue(status, 'Success')
    status = dev.wait_for_status(archive_url=self.archive_url_prefix)
    self.assertTrue(status, 'Success')
    self.mox.VerifyAll()

  def testBuildStaged(self):
    """Test whether we can correctly check if a build is previously staged."""
    base_url = 'gs://chrome-awesome/'
    build_dir = 'x86-awesome-release/R99-1234.0-r1'
    archive_url = base_url + build_dir
    archive_url_non_staged = base_url + 'x86-awesome-release/R99-1234.0-r2'
    # Create the directory to reflect staging.
    os.makedirs(os.path.join(self._work_dir, build_dir))

    self.assertTrue(downloader.Downloader.BuildStaged(archive_url,
                                                      self._work_dir))
    self.assertFalse(downloader.Downloader.BuildStaged(archive_url_non_staged,
                                                       self._work_dir))
  def testTrybotBuildStaged(self):
    """Test whether a previous staged trybot-build can be corrected detected"""
    base_url = 'gs://chrome-awesome/'
    build_dir = 'trybot/date/x86-awesome-release/R99-1234.0-r1'
    archive_url = base_url + build_dir
    archive_url_non_staged = base_url + 'x86-awesome-release/R99-1234.0-r2'
    # Create the directory to reflect staging.
    os.makedirs(os.path.join(self._work_dir, build_dir))

    self.assertTrue(downloader.Downloader.BuildStaged(archive_url,
                                                      self._work_dir))
    self.assertFalse(downloader.Downloader.BuildStaged(archive_url_non_staged,
                                                       self._work_dir))

class SymbolDownloaderTest(DownloaderTestBase):
  """Unit tests for downloader.SymbolDownloader.

  setUp() and tearDown() inherited from DownloaderTestBase.
  """

  def _CreateArtifactDownloader(self, artifacts):
    d = downloader.SymbolDownloader(self._work_dir)
    self.mox.StubOutWithMock(d, 'GatherArtifactDownloads')
    d.GatherArtifactDownloads(
        self._work_dir, self.archive_url_prefix, '',
        self._work_dir).AndReturn(artifacts)
    return d

  def _ClassUnderTest(self):
    return downloader.SymbolDownloader

  def _GenerateArtifacts(self, unused_ignore_background):
    """Instantiate artifact mocks and set expectations on them.

    Sets up a DebugTarball and sets up expectation that it will be
    downloaded and staged.

    @return iterable of one artifact object with appropriate expectations.
    """
    artifact = self.mox.CreateMock(downloadable_artifact.DownloadableArtifact)
    artifact.Synchronous = lambda: True
    artifact.Download()
    artifact.Stage()
    return [artifact]

  def testDownloaderSerially(self):
    """Runs through the symbol downloader workflow."""
    d = self._CreateArtifactDownloader(self._CommonDownloaderSetup())

    self.mox.ReplayAll()
    self.assertEqual(d.Download(self.archive_url_prefix), 'Success')
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
