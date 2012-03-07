#!/usr/bin/python
#
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for devserver_util module."""

import mox
import os
import shutil
import subprocess
import tempfile
import unittest

import devserver_util


# Fake Dev Server Layout:
TEST_LAYOUT = {
    'test-board-1': ['R17-1413.0.0-a1-b1346', 'R17-18.0.0-a1-b1346'],
    'test-board-2': ['R16-2241.0.0-a0-b2', 'R17-2.0.0-a1-b1346']
}


class DevServerUtilTest(mox.MoxTestBase):

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self._static_dir = tempfile.mkdtemp()
    self._outside_sandbox_dir = tempfile.mkdtemp()

    for board, builds in TEST_LAYOUT.iteritems():
      board_path = os.path.join(self._static_dir, board)
      os.mkdir(board_path)
      for build in builds:
        build_path = os.path.join(board_path, build)
        os.mkdir(build_path)
        with open(os.path.join(build_path,
                               devserver_util.TEST_IMAGE), 'w') as f:
          f.write('TEST_IMAGE')
        with open(os.path.join(build_path,
                               devserver_util.STATEFUL_UPDATE), 'w') as f:
          f.write('STATEFUL_UPDATE')
        with open(os.path.join(build_path,
                               devserver_util.ROOT_UPDATE), 'w') as f:
          f.write('ROOT_UPDATE')
        # AU payloads.
        au_dir = os.path.join(build_path, devserver_util.AU_BASE)
        nton_dir = os.path.join(au_dir, build + devserver_util.NTON_DIR_SUFFIX)
        os.makedirs(nton_dir)
        with open(os.path.join(nton_dir,
                               devserver_util.ROOT_UPDATE), 'w') as f:
          f.write('ROOT_UPDATE')
        mton_dir = os.path.join(au_dir, build + devserver_util.MTON_DIR_SUFFIX)
        os.makedirs(mton_dir)
        with open(os.path.join(mton_dir,
                               devserver_util.ROOT_UPDATE), 'w') as f:
          f.write('ROOT_UPDATE')

    self._good_mock_process = self.mox.CreateMock(subprocess.Popen)
    self._good_mock_process.returncode = 0
    self._bad_mock_process = self.mox.CreateMock(subprocess.Popen)
    self._bad_mock_process.returncode = 1

  def tearDown(self):
    shutil.rmtree(self._static_dir)
    shutil.rmtree(self._outside_sandbox_dir)

  def testParsePayloadList(self):
    archive_url_prefix = ('gs://chromeos-image-archive/x86-mario-release/'
                          'R17-1413.0.0-a1-b1346/')
    mton_url = (archive_url_prefix + 'chromeos_R17-1412.0.0-a1-b1345_'
                'R17-1413.0.0-a1_x86-mario_delta_dev.bin')
    nton_url = (archive_url_prefix + 'chromeos_R17-1413.0.0-a1_'
                'R17-1413.0.0-a1_x86-mario_delta_dev.bin')
    full_url = (archive_url_prefix + 'chromeos_R17-1413.0.0-a1_'
                'x86-mario_full_dev.bin')
    full_url_out, nton_url_out, mton_url_out = (
        devserver_util.ParsePayloadList([full_url, nton_url, mton_url]))
    self.assertEqual([full_url, nton_url, mton_url],
                     [full_url_out, nton_url_out, mton_url_out])

    archive_url_prefix = ('gs://chromeos-image-archive/x86-alex_he-release/'
                          'R18-1420.0.0-a1-b541')
    mton_url = (archive_url_prefix + 'chromeos_R18-1418.0.0-a1-b540_'
                'R18-1420.0.0-a1_x86-alex_he_delta_dev.bin')
    nton_url = (archive_url_prefix + 'chromeos_R18-1420.0.0-a1_'
                'R18-1420.0.0-a1_x86-alex_he_delta_dev.bin')
    full_url = (archive_url_prefix + 'chromeos_R18-1420.0.0-a1_'
                'x86-alex_he_full_dev.bin')
    full_url_out, nton_url_out, mton_url_out = (
        devserver_util.ParsePayloadList([full_url, nton_url, mton_url]))
    self.assertEqual([full_url, nton_url, mton_url],
                     [full_url_out, nton_url_out, mton_url_out])

  def _CallRunGS(self, output, str_should_contain, attempts=1):
    """Helper that wraps a RunGS for tests."""
    for attempt in range(attempts):
      if attempt == devserver_util.GSUTIL_ATTEMPTS:
        # We can't mock more than we can attempt.
        return

      # Return 1's for all but last attempt.
      if attempt != attempts - 1:
        mock_process = self._bad_mock_process
      else:
        mock_process = self._good_mock_process

      subprocess.Popen(mox.StrContains(str_should_contain), shell=True,
                       stdout=subprocess.PIPE).AndReturn(mock_process)
      mock_process.communicate().AndReturn((output, None))

  def testDownloadBuildFromGS(self):
    """Tests that we can run download build from gs with one error."""
    build = 'R17-1413.0.0-a1-b1346'
    archive_url_prefix = ('gs://chromeos-image-archive/x86-mario-release/' +
                          build)
    mock_data = 'mock data\nmock_data\nmock_data'
    payloads = ['p1', 'p2', 'p3']
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)
    self.mox.StubOutWithMock(devserver_util, 'ParsePayloadList')

    # Make sure we our retry works.
    self._CallRunGS(mock_data, archive_url_prefix, attempts=2)
    devserver_util.ParsePayloadList(mock_data.splitlines()).AndReturn(
        payloads)

    for payload in payloads + [devserver_util.STATEFUL_UPDATE,
                               devserver_util.AUTOTEST_PACKAGE]:
      self._CallRunGS(mock_data, payload,)

    self.mox.ReplayAll()
    devserver_util.DownloadBuildFromGS(self._static_dir, archive_url_prefix,
                                       build)
    self.mox.VerifyAll()

  def testDownloadBuildFromGSButGSDown(self):
    """Tests that we fail correctly if we can't reach GS."""
    build = 'R17-1413.0.0-a1-b1346'
    archive_url_prefix = ('gs://chromeos-image-archive/x86-mario-release/' +
                          build)
    mock_data = 'mock data\nmock_data\nmock_data'
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)

    self._CallRunGS(mock_data, archive_url_prefix,
                    attempts=devserver_util.GSUTIL_ATTEMPTS + 1)

    self.mox.ReplayAll()
    self.assertRaises(
        devserver_util.DevServerUtilError,
        devserver_util.DownloadBuildFromGS,
        self._static_dir, archive_url_prefix, build)
    self.mox.VerifyAll()

  def testInstallBuild(self):
    self.fail('Not implemented.')

  def testPrepareAutotestPkgs(self):
    self.fail('Not implemented.')

  def testSafeSandboxAccess(self):
    # Path is in sandbox.
    self.assertTrue(
        devserver_util.SafeSandboxAccess(
            self._static_dir, os.path.join(self._static_dir, 'some-board')))

    # Path is sandbox.
    self.assertFalse(
        devserver_util.SafeSandboxAccess(self._static_dir, self._static_dir))

    # Path is outside the sandbox.
    self.assertFalse(
        devserver_util.SafeSandboxAccess(self._static_dir,
                                         self._outside_sandbox_dir))

    # Path contains '..'.
    self.assertFalse(
        devserver_util.SafeSandboxAccess(
            self._static_dir, os.path.join(self._static_dir, os.pardir)))

    # Path contains symbolic link references.
    os.chdir(self._static_dir)
    os.symlink(os.pardir, 'parent')
    self.assertFalse(
        devserver_util.SafeSandboxAccess(
            self._static_dir, os.path.join(self._static_dir, os.pardir)))

  def testAcquireReleaseLocks(self):
    # Successful lock and unlock.
    lock_file = devserver_util.AcquireLock(self._static_dir, 'test-lock')
    self.assertTrue(os.path.exists(lock_file))
    devserver_util.ReleaseLock(self._static_dir, 'test-lock')
    self.assertFalse(os.path.exists(lock_file))

    # Attempt to lock an existing directory.
    devserver_util.AcquireLock(self._static_dir, 'test-lock')
    self.assertRaises(devserver_util.DevServerUtilError,
                      devserver_util.AcquireLock, self._static_dir, 'test-lock')

  def testFindMatchingBoards(self):
    for key in TEST_LAYOUT:
      # Partial match with multiple boards.
      self.assertEqual(
          set(devserver_util.FindMatchingBoards(self._static_dir, key[:-5])),
          set(TEST_LAYOUT.keys()))

      # Absolute match.
      self.assertEqual(
          devserver_util.FindMatchingBoards(self._static_dir, key), [key])

    # Invalid partial match.
    self.assertEqual(
        devserver_util.FindMatchingBoards(self._static_dir, 'asdfsadf'), [])

  def testFindMatchingBuilds(self):
    # Try a partial board and build match with single match.
    self.assertEqual(
        devserver_util.FindMatchingBuilds(self._static_dir, 'test-board',
                                          'R17-1413'),
        [('test-board-1', 'R17-1413.0.0-a1-b1346')])

    # Try a partial board and build match with multiple match.
    actual = set(devserver_util.FindMatchingBuilds(
        self._static_dir, 'test-board', 'R17'))
    expected = set([('test-board-1', 'R17-1413.0.0-a1-b1346'),
                    ('test-board-1', 'R17-18.0.0-a1-b1346'),
                    ('test-board-2', 'R17-2.0.0-a1-b1346')])
    self.assertEqual(actual, expected)

  def testGetLatestBuildVersion(self):
    self.assertEqual(
        devserver_util.GetLatestBuildVersion(self._static_dir, 'test-board-1'),
        'R17-1413.0.0-a1-b1346')

  def testFindBuild(self):
    # Ensure no matching boards raises exception for latest.
    self.assertRaises(
        devserver_util.DevServerUtilError, devserver_util.FindBuild,
        self._static_dir, 'aasdf', 'latest')

    # Ensure no matching builds or boards raises an exception.
    self.assertRaises(
        devserver_util.DevServerUtilError, devserver_util.FindBuild,
        self._static_dir, 'aasdf', 'asdgsadg')

    # Ensure latest returns the proper build.
    self.assertEqual(
        devserver_util.FindBuild(self._static_dir, 'test-board-1', 'latest'),
        ('test-board-1', 'R17-1413.0.0-a1-b1346'))

    # Ensure specific board, build is returned.
    self.assertEqual(
        devserver_util.FindBuild(self._static_dir, 'test-board-1',
                                 'R17-18.0.0-a1-b1346'),
        ('test-board-1', 'R17-18.0.0-a1-b1346'))

    # Ensure too many matches raises an exception.
    self.assertRaises(
        devserver_util.DevServerUtilError, devserver_util.FindBuild,
        self._static_dir, 'test-board', 'R17')

  def testCloneBuild(self):
    test_prefix = 'abc'
    test_tag = test_prefix + '/123'
    abc_path = os.path.join(self._static_dir, devserver_util.DEV_BUILD_PREFIX,
                            test_tag)

    os.mkdir(os.path.join(self._static_dir, test_prefix))

    # Verify leaf path is created and proper values returned.
    board, builds = TEST_LAYOUT.items()[0]
    dev_build = devserver_util.CloneBuild(self._static_dir, board, builds[0],
                                          test_tag)
    self.assertEquals(dev_build, abc_path)
    self.assertTrue(os.path.exists(abc_path))
    self.assertTrue(os.path.isfile(os.path.join(
        abc_path, devserver_util.TEST_IMAGE)))
    self.assertTrue(os.path.isfile(os.path.join(
        abc_path, devserver_util.ROOT_UPDATE)))
    self.assertTrue(os.path.isfile(os.path.join(
        abc_path, devserver_util.STATEFUL_UPDATE)))

    # Verify force properly removes the old directory.
    junk_path = os.path.join(dev_build, 'junk')
    with open(junk_path, 'w') as f:
      f.write('hello!')
    remote_dir = devserver_util.CloneBuild(
        self._static_dir, board, builds[0], test_tag, force=True)
    self.assertEquals(remote_dir, abc_path)
    self.assertTrue(os.path.exists(abc_path))
    self.assertTrue(os.path.isfile(os.path.join(
        abc_path, devserver_util.TEST_IMAGE)))
    self.assertTrue(os.path.isfile(os.path.join(
        abc_path, devserver_util.ROOT_UPDATE)))
    self.assertTrue(os.path.isfile(os.path.join(
        abc_path, devserver_util.STATEFUL_UPDATE)))
    self.assertFalse(os.path.exists(junk_path))

  def testGetControlFile(self):
    control_file_dir = os.path.join(
        self._static_dir, 'test-board-1', 'R17-1413.0.0-a1-b1346', 'autotest',
        'server', 'site_tests', 'network_VPN')
    os.makedirs(control_file_dir)
    with open(os.path.join(control_file_dir, 'control'), 'w') as f:
      f.write('hello!')

    control_content = devserver_util.GetControlFile(
        self._static_dir, 'test-board-1/R17-1413.0.0-a1-b1346',
        os.path.join('server', 'site_tests', 'network_VPN', 'control'))
    self.assertEqual(control_content, 'hello!')

  def testListAutoupdateTargets(self):
    for board, builds in TEST_LAYOUT.iteritems():
      for build in builds:
        au_targets = devserver_util.ListAutoupdateTargets(self._static_dir,
                                                          board, build)
        self.assertEqual(set(au_targets),
                         set([build + devserver_util.NTON_DIR_SUFFIX,
                              build + devserver_util.MTON_DIR_SUFFIX]))


if __name__ == '__main__':
  unittest.main()
