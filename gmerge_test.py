#!/usr/bin/python

# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for gmerge."""

import gmerge
import os
import unittest

class Flags(object):
  def __init__(self, dictionary):
    self.__dict__.update(dictionary)


class GMergeTest(unittest.TestCase):
  """Test for gmerge."""

  def setUp(self):
    self.lsb_release_lines = [
        'CHROMEOS_RELEASE_BOARD=x86-mario\r\n',
        'CHROMEOS_DEVSERVER=http://localhost:8080/\n']

  def testLsbRelease(self):
    merger = gmerge.GMerger(self.lsb_release_lines)
    self.assertEqual({'CHROMEOS_RELEASE_BOARD': 'x86-mario',
                      'CHROMEOS_DEVSERVER': 'http://localhost:8080/'},
                     merger.lsb_release)

  def testPostData(self):
    old_env = os.environ
    os.environ = {}
    os.environ['USE'] = 'a b c d +e'
    gmerge.FLAGS = Flags({'accept_stable': 'blah'})

    merger = gmerge.GMerger(self.lsb_release_lines)
    self.assertEqual(
        'use=a+b+c+d+%2Be&pkg=package_name&board=x86-mario&accept_stable=blah',
        merger.GeneratePackageRequest('package_name'))
    os.environ = old_env


if __name__ == '__main__':
  unittest.main()
