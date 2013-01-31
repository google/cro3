#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for common_util module."""

import os
import shutil
import tempfile
import unittest

import mox

import build_artifact
import common_util


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

    # Set up some basic existing structure used by GetLatest* tests.
    for board, builds in TEST_LAYOUT.iteritems():
      board_path = os.path.join(self._static_dir, board)
      os.mkdir(board_path)
      for build in builds:
        build_path = os.path.join(board_path, build)
        os.mkdir(build_path)
        with open(os.path.join(
          build_path, build_artifact.TEST_IMAGE_FILE), 'w') as f:
          f.write('TEST_IMAGE_FILE')
        with open(os.path.join(
          build_path, build_artifact.STATEFUL_UPDATE_FILE), 'w') as f:
          f.write('STATEFUL_UPDATE_FILE')
        with open(os.path.join(
          build_path, build_artifact.ROOT_UPDATE_FILE), 'w') as f:
          f.write('ROOT_UPDATE_FILE')

  def tearDown(self):
    shutil.rmtree(self._static_dir)
    shutil.rmtree(self._outside_sandbox_dir)

  def testPathInDir(self):
    """Various tests around the PathInDir test."""
    # Path is in sandbox.
    self.assertTrue(
        common_util.PathInDir(
            self._static_dir, os.path.join(self._static_dir, 'some-board')))

    # Path is sandbox.
    self.assertFalse(
        common_util.PathInDir(self._static_dir, self._static_dir))

    # Path is outside the sandbox.
    self.assertFalse(
        common_util.PathInDir(
          self._static_dir, self._outside_sandbox_dir))

    # Path contains '..'.
    self.assertFalse(
        common_util.PathInDir(
            self._static_dir, os.path.join(self._static_dir, os.pardir)))

    # Path contains symbolic link references.
    os.chdir(self._static_dir)
    os.symlink(os.pardir, 'parent')
    self.assertFalse(
        common_util.PathInDir(
            self._static_dir, os.path.join(self._static_dir, os.pardir)))

  def testGetLatestBuildVersion(self):
    """Tests that the latest version is correct given our setup."""
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
    """Creates a fake control file and verifies that we can get it."""
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


if __name__ == '__main__':
  unittest.main()
