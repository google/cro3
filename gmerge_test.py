#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for gmerge."""

import mox
import os
import unittest
import urllib2

import gmerge


class Flags(object):
  def __init__(self, dictionary):
    self.__dict__.update(dictionary)


class GMergeTest(mox.MoxTestBase):
  """Test for gmerge."""

  def setUp(self):
    super(GMergeTest, self).setUp()
    self.lsb_release_lines = [
        'CHROMEOS_RELEASE_BOARD=x86-mario\r\n',
        'CHROMEOS_DEVSERVER=http://localhost:8080/\n']

  def testLsbRelease(self):
    """Basic LSB release parsing test."""
    merger = gmerge.GMerger(None, None)
    merger.ParseLsbRelease(self.lsb_release_lines)
    self.assertEqual(merger.board_name, 'x86-mario')
    self.assertEqual(merger.devserver_url, 'http://localhost:8080/')

  def testLsbReleaseWithFlagsOverride(self):
    """Board/url values passed in to constructor should override parsed ones."""
    override_url = 'http://override:8080'
    override_board = 'override_board'
    merger = gmerge.GMerger(override_url, override_board)
    merger.ParseLsbRelease(self.lsb_release_lines)
    self.assertEqual(merger.board_name, override_board)
    self.assertEqual(merger.devserver_url, override_url)

  def testLsbReleaseWithMultipleKeyValCopies(self):
    """Lsb Release should only use the last val for any key=val combo."""
    override_url = 'http://override:8080'
    override_board = 'override_board'
    lsb_release_lines = self.lsb_release_lines + (
        ['CHROMEOS_RELEASE_BOARD=%s\r\n' % override_board,
         'CHROMEOS_DEVSERVER=%s\n' % override_url])
    merger = gmerge.GMerger(None, None)
    merger.ParseLsbRelease(lsb_release_lines)
    self.assertEqual(merger.board_name, override_board)
    self.assertEqual(merger.devserver_url, override_url)

  def testPostData(self):
    """Validate we construct the data url to the devserver correctly."""
    self.mox.StubOutWithMock(urllib2, 'urlopen')
    old_env = os.environ
    os.environ = {}
    os.environ['USE'] = 'a b c d +e'

    merger = gmerge.GMerger(None, None)
    merger.ParseLsbRelease(self.lsb_release_lines)

    # Expected post request.
    expected_data = ('use=a+b+c+d+%2Be&board=x86-mario&'
                     'deep=&pkg=package_name&usepkg=&accept_stable=blah')

    mock_object = self.mox.CreateMock(file)
    urllib2.urlopen(mox.IgnoreArg(), data=expected_data).AndReturn(mock_object)
    mock_object.read().AndReturn('Build succeeded')
    mock_object.close()
    self.mox.ReplayAll()
    merger.RequestPackageBuild('package_name', False, 'blah', False)
    self.mox.VerifyAll()
    os.environ = old_env


if __name__ == '__main__':
  unittest.main()
