#!/usr/bin/python
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for gsutil_util module."""

import mox
import subprocess
import time
import unittest

import gsutil_util


class GSUtilUtilTest(mox.MoxTestBase):

  def setUp(self):
    mox.MoxTestBase.setUp(self)

    self._good_mock_process = self.mox.CreateMock(subprocess.Popen)
    self._good_mock_process.returncode = 0
    self._bad_mock_process = self.mox.CreateMock(subprocess.Popen)
    self._bad_mock_process.returncode = 1
    self.mox.StubOutWithMock(time, 'sleep')
    time.sleep(mox.IgnoreArg()).MultipleTimes()

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

      subprocess.Popen(mox.StrContains(str_should_contain), shell=True,
                       stdout=subprocess.PIPE).AndReturn(mock_process)
      mock_process.communicate().AndReturn(('Does not matter', None))

  def testDownloadFromGS(self):
    """Tests that we can run download build from gs with one error."""
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)

    # Make sure we our retry works.
    self._CallRunGS('from to', attempts=2)
    self.mox.ReplayAll()
    gsutil_util.DownloadFromGS('from', 'to')
    self.mox.VerifyAll()

  def testDownloadFromGSButGSDown(self):
    """Tests that we fail correctly if we can't reach GS."""
    self.mox.StubOutWithMock(subprocess, 'Popen', use_mock_anything=True)
    self._CallRunGS('from to', attempts=gsutil_util.GSUTIL_ATTEMPTS + 1)

    self.mox.ReplayAll()
    self.assertRaises(
        gsutil_util.GSUtilError,
        gsutil_util.DownloadFromGS,
        'from', 'to')
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
