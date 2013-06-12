#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for xbuddy.py."""

import os
import shutil
import time
import unittest

import mox

import xbuddy

#pylint: disable=W0212
class xBuddyTest(mox.MoxTestBase):
  """Regression tests for xbuddy."""
  def setUp(self):
    mox.MoxTestBase.setUp(self)

    self.static_image_dir = '/tmp/static-dir/'

    self.mock_xb = xbuddy.XBuddy(self.static_image_dir)
    os.makedirs(self.static_image_dir)

  def tearDown(self):
    """Removes testing files."""
    shutil.rmtree(self.static_image_dir)

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
    path = "parrot-release/R27-2455.0.0/test"
    expected = ('parrot-release', 'R27-2455.0.0', 'test')
    self.assertEqual(self.mock_xb._InterpretPath(path=path), expected)

    path = "parrot-release/R27-2455.0.0/full_payload"
    expected = ('parrot-release', 'R27-2455.0.0', 'full_payload')
    self.assertEqual(self.mock_xb._InterpretPath(path=path), expected)

    path = "parrot-release/R27-2455.0.0/bad_alias"
    self.assertRaises(xbuddy.XBuddyException,
                      self.mock_xb._InterpretPath,
                      path=path)

  def testUnpackArgsWithVersionAliases(self):
    # TODO (joyc)
    pass

  def testLookupVersion(self):
    # TODO (joyc)
    pass

  def testTimestampsAndList(self):
    """Creation and listing of builds according to their timestamps."""
    # make 3 different timestamp files
    build_id11 = 'b1/v1'
    build_id12 = 'b1/v2'
    build_id23 = 'b2/v3'
    self.mock_xb._UpdateTimestamp(build_id11)
    time.sleep(0.5)
    self.mock_xb._UpdateTimestamp(build_id12)
    time.sleep(0.5)
    self.mock_xb._UpdateTimestamp(build_id23)

    # reference second one again
    time.sleep(0.5)
    self.mock_xb._UpdateTimestamp(build_id12)

    # check that list returns the same 3 things, in last referenced order
    result = self.mock_xb._ListBuilds()
    self.assertEqual(result[0][0], build_id12)
    self.assertEqual(result[1][0], build_id23)
    self.assertEqual(result[2][0], build_id11)

  ############### Public Methods
  def testXBuddyCaching(self):
    """Caching & replacement of timestamp files."""

    path_a = "a/latest-local/test"
    path_b = "b/latest-local/test"
    path_c = "c/latest-local/test"
    path_d = "d/latest-local/test"
    path_e = "e/latest-local/test"
    path_f = "f/latest-local/test"

    self.mox.StubOutWithMock(self.mock_xb, '_ResolveVersion')
    self.mox.StubOutWithMock(self.mock_xb, '_Download')
    for _ in range(8):
      self.mock_xb._ResolveVersion(mox.IsA(str),
                                   mox.IsA(str)).AndReturn('latest-local')
      self.mock_xb._Download(mox.IsA(str), mox.IsA(str))

    self.mox.ReplayAll()

    # requires default capacity
    self.assertEqual(self.mock_xb.Capacity(), '5')

    # Get 6 different images: a,b,c,d,e,f
    self.mock_xb.Get(path_a, None)
    time.sleep(0.5)
    self.mock_xb.Get(path_b, None)
    time.sleep(0.5)
    self.mock_xb.Get(path_c, None)
    time.sleep(0.5)
    self.mock_xb.Get(path_d, None)
    time.sleep(0.5)
    self.mock_xb.Get(path_e, None)
    time.sleep(0.5)
    self.mock_xb.Get(path_f, None)
    time.sleep(0.5)

    # check that b,c,d,e,f are still stored
    result = self.mock_xb._ListBuilds()
    self.assertEqual(len(result), 5)
    self.assertEqual(result[4][0], 'b/latest-local')
    self.assertEqual(result[3][0], 'c/latest-local')
    self.assertEqual(result[2][0], 'd/latest-local')
    self.assertEqual(result[1][0], 'e/latest-local')
    self.assertEqual(result[0][0], 'f/latest-local')

    # Get b,a
    self.mock_xb.Get(path_b, None)
    time.sleep(0.5)
    self.mock_xb.Get(path_a, None)
    time.sleep(0.5)

    # check that d,e,f,b,a are still stored
    result = self.mock_xb._ListBuilds()
    self.assertEqual(len(result), 5)
    self.assertEqual(result[4][0], 'd/latest-local')
    self.assertEqual(result[3][0], 'e/latest-local')
    self.assertEqual(result[2][0], 'f/latest-local')
    self.assertEqual(result[1][0], 'b/latest-local')
    self.assertEqual(result[0][0], 'a/latest-local')

    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
