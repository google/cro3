#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for common_util module."""

import os
import shutil
import subprocess
import tempfile
import unittest

import mox

import build_artifact
import common_util
import gsutil_util


# Fake Dev Server Layout:
TEST_LAYOUT = {
    'test-board-1': ['R17-1413.0.0-a1-b1346', 'R17-18.0.0-a1-b1346'],
    'test-board-2': ['R16-2241.0.0-a0-b2', 'R17-2.0.0-a1-b1346'],
    'test-board-3': []
}


class CommonUtilTest(mox.MoxTestBase):

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self._static_dir = tempfile.mkdtemp('common_util_unittest')
    self._outside_sandbox_dir = tempfile.mkdtemp('common_util_unittest')
    self._install_dir = tempfile.mkdtemp('common_util_unittest')

    for board, builds in TEST_LAYOUT.iteritems():
      board_path = os.path.join(self._static_dir, board)
      os.mkdir(board_path)
      for build in builds:
        build_path = os.path.join(board_path, build)
        os.mkdir(build_path)
        with open(os.path.join(
          build_path, build_artifact.TEST_IMAGE), 'w') as f:
          f.write('TEST_IMAGE')
        with open(os.path.join(
          build_path, build_artifact.STATEFUL_UPDATE), 'w') as f:
          f.write('STATEFUL_UPDATE')
        with open(os.path.join(
          build_path, build_artifact.ROOT_UPDATE), 'w') as f:
          f.write('ROOT_UPDATE')
        # AU payloads.
        au_dir = os.path.join(build_path, common_util.AU_BASE)
        nton_dir = os.path.join(au_dir, build + common_util.NTON_DIR_SUFFIX)
        os.makedirs(nton_dir)
        with open(os.path.join(nton_dir, build_artifact.ROOT_UPDATE), 'w') as f:
          f.write('ROOT_UPDATE')
        mton_dir = os.path.join(au_dir, build + common_util.MTON_DIR_SUFFIX)
        os.makedirs(mton_dir)
        with open(os.path.join(mton_dir, build_artifact.ROOT_UPDATE), 'w') as f:
          f.write('ROOT_UPDATE')

    self._good_mock_process = self.mox.CreateMock(subprocess.Popen)
    self._good_mock_process.returncode = 0
    self._bad_mock_process = self.mox.CreateMock(subprocess.Popen)
    self._bad_mock_process.returncode = 1

  def tearDown(self):
    shutil.rmtree(self._static_dir)
    shutil.rmtree(self._outside_sandbox_dir)
    shutil.rmtree(self._install_dir)

  def testParsePayloadListWithoutDeltas(self):
    """Tests we can parse the payload list when no delta updates exist."""
    archive_url_prefix = ('gs://chromeos-image-archive/x86-mario-release/'
                          'R17-1413.0.0-a1-b1346')
    full_basename = ('chromeos_R17-1413.0.0-a1_x86-mario_full_dev.bin')
    full_url = '/'.join([archive_url_prefix, full_basename])
    full_url_out, nton_url_out, mton_url_out = (
        common_util.ParsePayloadList(
            archive_url_prefix, [full_basename, '', '']))
    self.assertEqual([full_url, None, None],
                     [full_url_out, nton_url_out, mton_url_out])

  def testParsePartialPayloadList(self):
    """Tests that we can parse a payload list with missing optional payload."""
    archive_url_prefix = ('gs://chromeos-image-archive/x86-mario-release/'
                          'R17-1413.0.0-a1-b1346/')
    nton_basename = ('chromeos_R17-1413.0.0-a1_R17-1413.0.0-a1_x86-'
                     'mario_delta_dev.bin')
    full_basename = ('chromeos_R17-1413.0.0-a1_x86-mario_full_dev.bin')

    nton_url = '/'.join([archive_url_prefix, nton_basename])
    full_url = '/'.join([archive_url_prefix, full_basename])

    full_url_out, nton_url_out, mton_url_out = (
        common_util.ParsePayloadList(archive_url_prefix,
                                     [full_basename, nton_basename]))
    self.assertEqual([full_url, nton_url, None],
                     [full_url_out, nton_url_out, mton_url_out])

  def testInstallBuild(self):
    # TODO(frankf): Implement this test
    # self.fail('Not implemented.')
    pass

  def testPrepareAutotestPkgs(self):
    # TODO(frankf): Implement this test
    # self.fail('Not implemented.')
    # TODO: implement
    pass

  def testSafeSandboxAccess(self):
    # Path is in sandbox.
    self.assertTrue(
        common_util.SafeSandboxAccess(
            self._static_dir, os.path.join(self._static_dir, 'some-board')))

    # Path is sandbox.
    self.assertFalse(
        common_util.SafeSandboxAccess(self._static_dir, self._static_dir))

    # Path is outside the sandbox.
    self.assertFalse(
        common_util.SafeSandboxAccess(
          self._static_dir, self._outside_sandbox_dir))

    # Path contains '..'.
    self.assertFalse(
        common_util.SafeSandboxAccess(
            self._static_dir, os.path.join(self._static_dir, os.pardir)))

    # Path contains symbolic link references.
    os.chdir(self._static_dir)
    os.symlink(os.pardir, 'parent')
    self.assertFalse(
        common_util.SafeSandboxAccess(
            self._static_dir, os.path.join(self._static_dir, os.pardir)))

  def testAcquireReleaseLocks(self):
    # Successful lock and unlock, removing the newly created directory.
    lock_file = common_util.AcquireLock(self._static_dir, 'test-lock')
    self.assertTrue(os.path.exists(lock_file))
    common_util.ReleaseLock(self._static_dir, 'test-lock', destroy=True)
    self.assertFalse(os.path.exists(lock_file))

    # Attempt to freshly create and lock an existing directory.
    common_util.AcquireLock(self._static_dir, 'test-lock')
    common_util.ReleaseLock(self._static_dir, 'test-lock')
    self.assertRaises(common_util.CommonUtilError, common_util.AcquireLock,
                      self._static_dir, 'test-lock')
    common_util.AcquireLock(self._static_dir, 'test-lock', create_once=False)
    common_util.ReleaseLock(self._static_dir, 'test-lock', destroy=True)

    # Sucessfully re-lock a pre-existing directory.
    common_util.AcquireLock(self._static_dir, 'test-lock')
    common_util.ReleaseLock(self._static_dir, 'test-lock')
    common_util.AcquireLock(self._static_dir, 'test-lock', create_once=False)
    common_util.ReleaseLock(self._static_dir, 'test-lock', destroy=True)

    # Attempt to lock an already locked directory.
    common_util.AcquireLock(self._static_dir, 'test-lock')
    self.assertRaises(common_util.CommonUtilError, common_util.AcquireLock,
                      self._static_dir, 'test-lock')
    common_util.ReleaseLock(self._static_dir, 'test-lock', destroy=True)

  def testGetLatestBuildVersion(self):
    self.assertEqual(
        common_util.GetLatestBuildVersion(self._static_dir, 'test-board-1'),
        'R17-1413.0.0-a1-b1346')

  def testGetLatestBuildVersionLatest(self):
    """Test that we raise CommonUtilError when a build dir is empty."""
    self.assertRaises(common_util.CommonUtilError,
                      common_util.GetLatestBuildVersion,
                      self._static_dir, 'test-board-3')

  def testGetLatestBuildVersionUnknownBuild(self):
    """Test that we raise CommonUtilError when a build dir does not exist."""
    self.assertRaises(common_util.CommonUtilError,
                      common_util.GetLatestBuildVersion,
                      self._static_dir, 'bad-dir')

  def testGetLatestBuildVersionMilestone(self):
    """Test that we can get builds based on milestone."""
    expected_build_str = 'R16-2241.0.0-a0-b2'
    milestone = 'R16'
    build_str = common_util.GetLatestBuildVersion(
        self._static_dir, 'test-board-2', milestone)
    self.assertEqual(expected_build_str, build_str)

  def testGetControlFile(self):
    control_file_dir = os.path.join(
        self._static_dir, 'test-board-1', 'R17-1413.0.0-a1-b1346', 'autotest',
        'server', 'site_tests', 'network_VPN')
    os.makedirs(control_file_dir)
    with open(os.path.join(control_file_dir, 'control'), 'w') as f:
      f.write('hello!')

    control_content = common_util.GetControlFile(
        self._static_dir, 'test-board-1/R17-1413.0.0-a1-b1346',
        os.path.join('server', 'site_tests', 'network_VPN', 'control'))
    self.assertEqual(control_content, 'hello!')

  def testGatherArtifactDownloads(self):
    """Tests that we can gather the correct download requirements."""
    build = 'R17-1413.0.0-a1-b1346'
    archive_url_prefix = ('gs://chromeos-image-archive/x86-mario-release/' +
                          build)
    mock_data = 'mock data\nmock_data'
    payloads = map(lambda x: '/'.join([archive_url_prefix, x]),
                   ['p1', 'p2', 'p3'])
    expected_payloads = payloads + map(
        lambda x: '/'.join([archive_url_prefix, x]),
            [build_artifact.STATEFUL_UPDATE,
             build_artifact.AUTOTEST_ZIPPED_PACKAGE,
             build_artifact.TEST_SUITES_PACKAGE])
    self.mox.StubOutWithMock(gsutil_util, 'GSUtilRun')
    self.mox.StubOutWithMock(common_util, 'IsAvailable')
    self.mox.StubOutWithMock(common_util, 'ParsePayloadList')

    # GSUtil cat gs://archive_url_prefix/UPLOADED.
    gsutil_util.GSUtilRun(mox.StrContains(common_util.UPLOADED_LIST),
                          mox.IgnoreArg()).AndReturn(mock_data)
    common_util.IsAvailable(
        mox.IgnoreArg(), mock_data.splitlines()).AndReturn(True)
    common_util.ParsePayloadList(archive_url_prefix,
                                 mock_data.splitlines()).AndReturn(payloads)

    self.mox.ReplayAll()
    artifacts = common_util.GatherArtifactDownloads(
        self._static_dir, archive_url_prefix, self._install_dir, build)
    for index, artifact in enumerate(artifacts):
      self.assertEqual(artifact._gs_path, expected_payloads[index])
      self.assertTrue(artifact._tmp_staging_dir.startswith(self._static_dir))

    self.mox.VerifyAll()

  def testGatherArtifactDownloadsWithoutMton(self):
    """Gather the correct download requirements without mton delta."""
    build = 'R17-1413.0.0-a1-b1346'
    archive_url_prefix = ('gs://chromeos-image-archive/x86-mario-release/' +
                          build)
    mock_data = 'mock data\nmock_data\nmock_data'
    payloads = map(lambda x: '/'.join([archive_url_prefix, x]),
                   ['p1', 'p2'])
    expected_payloads = payloads + map(
        lambda x: '/'.join([archive_url_prefix, x]),
            [build_artifact.STATEFUL_UPDATE,
             build_artifact.AUTOTEST_ZIPPED_PACKAGE,
             build_artifact.TEST_SUITES_PACKAGE])
    self.mox.StubOutWithMock(gsutil_util, 'GSUtilRun')
    self.mox.StubOutWithMock(common_util, 'IsAvailable')
    self.mox.StubOutWithMock(common_util, 'ParsePayloadList')

    # GSUtil cat gs://archive_url_prefix/UPLOADED.
    gsutil_util.GSUtilRun(mox.StrContains(common_util.UPLOADED_LIST),
                          mox.IgnoreArg()).AndReturn(mock_data)
    common_util.IsAvailable(
        mox.IgnoreArg(), mock_data.splitlines()).AndReturn(True)
    common_util.ParsePayloadList(archive_url_prefix,
                                 mock_data.splitlines()
                                 ).AndReturn(payloads + [None])

    self.mox.ReplayAll()
    artifacts = common_util.GatherArtifactDownloads(
        self._static_dir, archive_url_prefix, self._install_dir, build)
    for index, artifact in enumerate(artifacts):
      self.assertEqual(artifact._gs_path, expected_payloads[index])
      self.assertTrue(artifact._tmp_staging_dir.startswith(self._static_dir))

    self.mox.VerifyAll()

  def testGatherArtifactDownloadsWithoutMtonOrNton(self):
    """Gather the correct download requirements without delta payloads."""
    build = 'R17-1413.0.0-a1-b1346'
    archive_url_prefix = ('gs://chromeos-image-archive/x86-mario-release/' +
                          build)
    mock_data = 'mock data\nmock_data'

    payloads = map(lambda x: '/'.join([archive_url_prefix, x]),
                   ['p1'])
    expected_payloads = payloads + map(
        lambda x: '/'.join([archive_url_prefix, x]),
            [build_artifact.STATEFUL_UPDATE,
             build_artifact.AUTOTEST_ZIPPED_PACKAGE,
             build_artifact.TEST_SUITES_PACKAGE])
    self.mox.StubOutWithMock(gsutil_util, 'GSUtilRun')
    self.mox.StubOutWithMock(common_util, 'IsAvailable')
    self.mox.StubOutWithMock(common_util, 'ParsePayloadList')

    # GSUtil cat gs://archive_url_prefix/UPLOADED.
    gsutil_util.GSUtilRun(mox.StrContains(common_util.UPLOADED_LIST),
                          mox.IgnoreArg()).AndReturn(mock_data)
    common_util.IsAvailable(
        mox.IgnoreArg(), mock_data.splitlines()).AndReturn(True)
    common_util.ParsePayloadList(archive_url_prefix,
                                 mock_data.splitlines()
                                 ).AndReturn(payloads + [None, None])

    self.mox.ReplayAll()
    artifacts = common_util.GatherArtifactDownloads(
        self._static_dir, archive_url_prefix, self._install_dir, build)
    for index, artifact in enumerate(artifacts):
      self.assertEqual(artifact._gs_path, expected_payloads[index])
      self.assertTrue(artifact._tmp_staging_dir.startswith(self._static_dir))

    self.mox.VerifyAll()

  def testGatherSymbolArtifactDownloads(self):
    """Tests that we can find debug symbol artifacts to download."""
    build = 'R17-1413.0.0-a1-b1346'
    archive_url_prefix = ('gs://chromeos-image-archive/x86-mario-release/' +
                          build)
    symbol_url = '/'.join([archive_url_prefix,
                           build_artifact.DEBUG_SYMBOLS])
    uploaded_list_url = '/'.join([archive_url_prefix,
                                  common_util.UPLOADED_LIST])
    mock_data = 'mock-tarball.tgz\nmock-debug.tgz'
    self.mox.StubOutWithMock(gsutil_util, 'GSUtilRun')

    # GSUtil cat gs://archive_url_prefix/UPLOADED.
    gsutil_util.GSUtilRun(mox.StrContains(common_util.UPLOADED_LIST),
                          mox.IgnoreArg()).AndReturn(mock_data)

    self.mox.ReplayAll()
    artifacts = common_util.GatherSymbolArtifactDownloads(
        self._static_dir, archive_url_prefix, self._install_dir)
    for index, artifact in enumerate(artifacts):
      self.assertEqual(artifact._gs_path, symbol_url)
      self.assertTrue(artifact._tmp_staging_dir.startswith(self._static_dir))

    self.mox.VerifyAll()

  def testIsAvailable(self):
    """Test that we can detect whether the target artifacts are avaialble."""
    # Test when the all target files are available
    pattern_list = ['_full_', 'autotest.tar']
    uploaded_list = ['chromeos_R17-1413.0.0-a1_x86-mario_full_dev.bin',
                     'debug.tgz',
                     'autotest.tar.bz2']

    available = common_util.IsAvailable(pattern_list, uploaded_list)
    self.assertTrue(available)

    # Test when some target files are missing
    pattern_list = ['_full_', 'autotest.tar']
    uploaded_list = ['chromeos_R17-1413.0.0-a1_x86-mario_full_dev.bin',
                     'debug.tgz']

    available = common_util.IsAvailable(pattern_list, uploaded_list)
    self.assertFalse(available)

  def testWaitUntilAvailable(self):
    """Test that we can poll until all target artifacts are available."""
    build = 'R17-1413.0.0-a1-b1346'
    archive_url = ('gs://chromeos-image-archive/x86-mario-release/'
                   'R17-1413.0.0-a1-b1346')
    to_wait_list = ['_full_']
    mock_data = 'mock data\nmock_data\nmock_data'

    self.mox.StubOutWithMock(gsutil_util, 'GSUtilRun')
    self.mox.StubOutWithMock(common_util, 'IsAvailable')

    # GSUtil cat gs://archive_url_prefix/UPLOADED.
    gsutil_util.GSUtilRun(mox.StrContains(common_util.UPLOADED_LIST),
                          mox.IgnoreArg()).AndReturn(mock_data)
    common_util.IsAvailable(mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(True)

    self.mox.ReplayAll()
    uploaded_list = common_util.WaitUntilAvailable(
        to_wait_list, archive_url, 'UNIT TEST', delay=1)
    self.assertEqual(uploaded_list, mock_data.splitlines())
    self.mox.VerifyAll()

  def testWaitUntilAvailableWithRetry(self):
    """Test that we can poll until all target artifacts are available."""
    build = 'R17-1413.0.0-a1-b1346'
    archive_url = ('gs://chromeos-image-archive/x86-mario-release/'
                   'R17-1413.0.0-a1-b1346')
    to_wait_list = ['_full_']
    mock_data = 'mock data\nmock_data\nmock_data'

    self.mox.StubOutWithMock(gsutil_util, 'GSUtilRun')
    self.mox.StubOutWithMock(common_util, 'IsAvailable')

    # GSUtil cat gs://archive_url_prefix/UPLOADED.
    gsutil_util.GSUtilRun(mox.StrContains(common_util.UPLOADED_LIST),
                          mox.IgnoreArg()).AndReturn(mock_data)
    common_util.IsAvailable(mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(False)

    gsutil_util.GSUtilRun(mox.StrContains(common_util.UPLOADED_LIST),
                          mox.IgnoreArg()).AndReturn(mock_data)
    common_util.IsAvailable(mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(True)

    self.mox.ReplayAll()
    uploaded_list = common_util.WaitUntilAvailable(
        to_wait_list, archive_url, 'UNIT TEST', delay=1)
    self.assertEqual(uploaded_list, mock_data.splitlines())
    self.mox.VerifyAll()

  def testWaitUntilAvailableTimeout(self):
    """Test that we wait for the target artifacts until timeout occurs."""
    build = 'R17-1413.0.0-a1-b1346'
    archive_url = ('gs://chromeos-image-archive/x86-mario-release/'
                   'R17-1413.0.0-a1-b1346')
    to_wait_list = ['_full_']
    mock_data = 'mock data\nmock_data\nmock_data'

    self.mox.StubOutWithMock(gsutil_util, 'GSUtilRun')
    self.mox.StubOutWithMock(common_util, 'IsAvailable')

    # GSUtil cat gs://archive_url_prefix/UPLOADED.
    gsutil_util.GSUtilRun(mox.StrContains(common_util.UPLOADED_LIST),
                          mox.IgnoreArg()).AndReturn(mock_data)
    common_util.IsAvailable(mox.IgnoreArg(), mox.IgnoreArg()).AndReturn(False)

    self.mox.ReplayAll()
    self.assertRaises(common_util.CommonUtilError,
                      common_util.WaitUntilAvailable,
                      to_wait_list,
                      archive_url,
                      'UNIT TEST',
                      delay=2,
                      timeout=1)
    self.mox.VerifyAll()

if __name__ == '__main__':
  unittest.main()
