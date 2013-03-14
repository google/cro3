#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for gsutil_util module."""

import subprocess
import time
import unittest

import mox

import gsutil_util


# pylint: disable=W0212
class GSUtilUtilTest(mox.MoxTestBase):

  def setUp(self):
    mox.MoxTestBase.setUp(self)

    self._good_mock_process = self.mox.CreateMock(subprocess.Popen)
    self._good_mock_process.returncode = 0
    self._bad_mock_process = self.mox.CreateMock(subprocess.Popen)
    self._bad_mock_process.returncode = 1

  def _CallRunGS(self, str_should_contain, attempts=1):
    """Helper that wraps a RunGS for tests."""
    for attempt in range(attempts):
      if attempt == gsutil_util.GSUTIL_ATTEMPTS:
        # We can't mock more than we can attempt.
        return

      # Return 1's for all but last attempt.
      if attempt != attempts - 1:
        mock_process = self._bad_mock_process
      else:
        mock_process = self._good_mock_process

      subprocess.Popen(mox.StrContains(str_should_contain),
                       shell=True, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE).AndReturn(mock_process)
      mock_process.communicate().AndReturn(('Does not matter', None))

  def testDownloadFromGS(self):
    """Tests that we can run download build from gs with one error."""
    self.mox.StubOutWithMock(time, 'sleep')
    time.sleep(mox.IgnoreArg()).MultipleTimes()
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)

    # Make sure we our retry works.
    self._CallRunGS('from to', attempts=2)
    self.mox.ReplayAll()
    gsutil_util.DownloadFromGS('from', 'to')
    self.mox.VerifyAll()

  def testDownloadFromGSButGSDown(self):
    """Tests that we fail correctly if we can't reach GS."""
    self.mox.StubOutWithMock(time, 'sleep')
    time.sleep(mox.IgnoreArg()).MultipleTimes()
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)
    self._CallRunGS('from to', attempts=gsutil_util.GSUTIL_ATTEMPTS + 1)

    self.mox.ReplayAll()
    self.assertRaises(
        gsutil_util.GSUtilError,
        gsutil_util.DownloadFromGS,
        'from', 'to')
    self.mox.VerifyAll()

  def testGSNamesFromList(self):
    """Test that we can detect whether the target artifacts are available."""
    # Test when the all target files are available
    pattern = '.*_full_.*'
    uploaded_list = ['chromeos_R17-1413.0.0-a1_x86-mario_full_dev.bin',
                     'debug.tgz',
                     'autotest.tar.bz2']

    names = gsutil_util._GetGSNamesFromList(uploaded_list, pattern)
    self.assertEqual(names[0],
                     'chromeos_R17-1413.0.0-a1_x86-mario_full_dev.bin')

    bad_pattern = '_delta_'
    # Test when some target files are missing
    names = gsutil_util._GetGSNamesFromList(uploaded_list, bad_pattern)
    self.assertEqual(names, [])

  def testGetGSNamesWithWait(self):
    """Test that we get the target artifact that is available."""
    archive_url = ('gs://chromeos-image-archive/x86-mario-release/'
                   'R17-1413.0.0-a1-b1346')
    name = 'chromeos_R17-1413.0.0-a1_x86-mario_full_dev.bin'
    pattern = '_full_'
    mock_data = 'mock data\nmock_data\nmock_data'
    msg = 'UNIT TEST'

    self.mox.StubOutWithMock(gsutil_util, 'GSUtilRun')
    self.mox.StubOutWithMock(gsutil_util, '_GetGSNamesFromList')

    # GSUtil cat gs://archive_url_prefix/UPLOADED.
    gsutil_util.GSUtilRun(mox.StrContains(gsutil_util.UPLOADED_LIST),
                          mox.IgnoreArg()).AndReturn(mock_data)
    gsutil_util._GetGSNamesFromList(mock_data.split('\n'),
                                    pattern).AndReturn([name])

    self.mox.ReplayAll()
    # Timeout explicitly set to 0 to test that we always run at least once.
    returned_names = gsutil_util.GetGSNamesWithWait(
        pattern, archive_url, msg, delay=1, timeout=0)
    self.assertEqual([name], returned_names)
    self.mox.VerifyAll()

  def testGetGSNamesWithWaitWithRetry(self):
    """Test that we can poll until all target artifacts are available."""
    archive_url = ('gs://chromeos-image-archive/x86-mario-release/'
                   'R17-1413.0.0-a1-b1346')
    name = 'chromeos_R17-1413.0.0-a1_x86-mario_full_dev.bin'
    pattern = '_full_'
    mock_data = 'mock data\nmock_data\nmock_data'
    msg = 'UNIT TEST'

    self.mox.StubOutWithMock(gsutil_util, 'GSUtilRun')
    self.mox.StubOutWithMock(gsutil_util, '_GetGSNamesFromList')

    # GSUtil cat gs://archive_url_prefix/UPLOADED.
    gsutil_util.GSUtilRun(mox.StrContains(gsutil_util.UPLOADED_LIST),
                          mox.IgnoreArg()).AndReturn(mock_data)
    gsutil_util._GetGSNamesFromList(mock_data.split('\n'),
                                   pattern).AndReturn(None)

    gsutil_util.GSUtilRun(mox.StrContains(gsutil_util.UPLOADED_LIST),
                          mox.IgnoreArg()).AndReturn(mock_data)
    gsutil_util._GetGSNamesFromList(mox.IgnoreArg(),
                                    mox.IgnoreArg()).AndReturn([name])

    self.mox.ReplayAll()
    returned_names = gsutil_util.GetGSNamesWithWait(
        pattern, archive_url, msg, delay=1, timeout=3)
    self.assertEqual(name, returned_names[0])
    self.mox.VerifyAll()

  def testGetGSNamesWithWaitTimeout(self):
    """Test that we wait for the target artifacts until timeout occurs."""
    archive_url = ('gs://chromeos-image-archive/x86-mario-release/'
                   'R17-1413.0.0-a1-b1346')
    pattern = '_full_'
    mock_data = 'mock data\nmock_data\nmock_data'
    msg = 'UNIT TEST'

    self.mox.StubOutWithMock(gsutil_util, 'GSUtilRun')
    self.mox.StubOutWithMock(gsutil_util, '_GetGSNamesFromList')

    # GSUtil cat gs://archive_url_prefix/UPLOADED.
    gsutil_util.GSUtilRun(mox.StrContains(gsutil_util.UPLOADED_LIST),
                          mox.IgnoreArg()).AndReturn(mock_data)
    gsutil_util._GetGSNamesFromList(mock_data.split('\n'),
                                    pattern).AndReturn(None)

    self.mox.ReplayAll()
    returned_name = gsutil_util.GetGSNamesWithWait(
        pattern, archive_url, msg, delay=2, timeout=1)
    self.assertEqual(returned_name, None)
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
