#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for xbuddy.py."""

import os
import shutil
import tempfile
import time
import unittest

import mox

import xbuddy

#pylint: disable=W0212
class xBuddyTest(mox.MoxTestBase):
  """Regression tests for xbuddy."""
  def setUp(self):
    mox.MoxTestBase.setUp(self)

    self.static_image_dir = tempfile.mkdtemp('xbuddy_unittest_static')
    self.root_dir = tempfile.mkdtemp('xbuddy_unittest_ds_root')

    self.mock_xb = xbuddy.XBuddy(
      root_dir=self.root_dir,
      static_dir=self.static_image_dir
    )
    self.images_dir = tempfile.mkdtemp('xbuddy_unittest_images')
    self.mock_xb.images_dir = self.images_dir

  def tearDown(self):
    """Removes testing files."""
    shutil.rmtree(self.static_image_dir)
    shutil.rmtree(self.images_dir)

  def testParseBoolean(self):
    """Check that some common True/False strings are handled."""
    self.assertEqual(xbuddy.XBuddy.ParseBoolean(None), False)
    self.assertEqual(xbuddy.XBuddy.ParseBoolean('false'), False)
    self.assertEqual(xbuddy.XBuddy.ParseBoolean('bs'), False)
    self.assertEqual(xbuddy.XBuddy.ParseBoolean('true'), True)
    self.assertEqual(xbuddy.XBuddy.ParseBoolean('y'), True)

  def _testResolveVersion(self):
    # TODO (joyc)
    pass

  def testBasicInterpretPath(self):
    """Basic checks for splitting a path"""
    path = ('parrot-release', 'R27-2455.0.0', 'test')
    expected = ('parrot-release', 'R27-2455.0.0', 'test')
    self.assertEqual(self.mock_xb._InterpretPath(path_list=path), expected)

    path = ('parrot-release', 'R27-2455.0.0', 'full_payload')
    expected = ('parrot-release', 'R27-2455.0.0', 'full_payload')
    self.assertEqual(self.mock_xb._InterpretPath(path_list=path), expected)

    path = ('parrot-release', 'R27-2455.0.0')
    expected = ('parrot-release', 'R27-2455.0.0', 'test')
    self.assertEqual(self.mock_xb._InterpretPath(path_list=path), expected)

    path = ('parrot-release', 'R27-2455.0.0', 'too', 'many', 'pieces')
    self.assertRaises(xbuddy.XBuddyException,
                      self.mock_xb._InterpretPath,
                      path_list=path)


  def testLookupVersion(self):
    # TODO (joyc)
    pass

  def testTimestampsAndList(self):
    """Creation and listing of builds according to their timestamps."""
    # make 3 different timestamp files
    b_id11 = 'b1/v1'
    b_id12 = 'b1/v2'
    b_id23 = 'b2/v3'
    xbuddy.Timestamp.UpdateTimestamp(self.mock_xb._timestamp_folder, b_id11)
    time.sleep(0.05)
    xbuddy.Timestamp.UpdateTimestamp(self.mock_xb._timestamp_folder, b_id12)
    time.sleep(0.05)
    xbuddy.Timestamp.UpdateTimestamp(self.mock_xb._timestamp_folder, b_id23)

    # reference second one again
    time.sleep(0.05)
    xbuddy.Timestamp.UpdateTimestamp(self.mock_xb._timestamp_folder, b_id12)

    # check that list returns the same 3 things, in last referenced order
    result = self.mock_xb._ListBuildTimes()
    self.assertEqual(result[0][0], b_id12)
    self.assertEqual(result[1][0], b_id23)
    self.assertEqual(result[2][0], b_id11)

  def testSyncRegistry(self):
    # check that there are no builds initially
    result = self.mock_xb._ListBuildTimes()
    self.assertEqual(len(result), 0)

    # set up the dummy build/images directory with images
    boards = ['a', 'b']
    versions = ['v1', 'v2']
    for b in boards:
      os.makedirs(os.path.join(self.mock_xb.images_dir, b))
      for v in versions:
        os.makedirs(os.path.join(self.mock_xb.images_dir, b, v))

    # Sync and check that they've been added to xBuddy's registry
    self.mock_xb._SyncRegistryWithBuildImages()
    result = self.mock_xb._ListBuildTimes()
    self.assertEqual(len(result), 4)

  ############### Public Methods
  def testXBuddyCaching(self):
    """Caching & replacement of timestamp files."""
    path_a = ('a', 'R0', 'test')
    path_b = ('b', 'R0', 'test')

    self.mox.StubOutWithMock(self.mock_xb, '_ResolveVersion')
    self.mox.StubOutWithMock(self.mock_xb, '_Download')
    for _ in range(8):
      self.mock_xb._ResolveVersion(mox.IsA(str),
                                   mox.IsA(str)).AndReturn('R0')
      self.mock_xb._Download(mox.IsA(str), mox.IsA(str))

    self.mox.ReplayAll()

    # requires default capacity
    self.assertEqual(self.mock_xb.Capacity(), '5')

    # Get 6 different images: a,b,c,d,e,f
    images = ['a', 'b', 'c', 'd', 'e', 'f']
    for c in images:
      self.mock_xb.Get((c, 'R0', 'test'), None)
      time.sleep(0.05)

    # check that b,c,d,e,f are still stored
    result = self.mock_xb._ListBuildTimes()
    self.assertEqual(len(result), 5)

    # Flip the list to get reverse chronological order
    images.reverse()
    for i in range(5):
      self.assertEqual(result[i][0], '%s/R0' % images[i])

    # Get b,a
    self.mock_xb.Get(path_b, None)
    time.sleep(0.05)
    self.mock_xb.Get(path_a, None)
    time.sleep(0.05)

    # check that d,e,f,b,a are still stored
    result = self.mock_xb._ListBuildTimes()
    self.assertEqual(len(result), 5)
    images_expected = ['a', 'b', 'f', 'e', 'd']
    for i in range(5):
      self.assertEqual(result[i][0], '%s/R0' % images_expected[i])

    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
