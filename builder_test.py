#!/usr/bin/python
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import subprocess
import unittest

import builder


class BuilderTest(unittest.TestCase):
  def testOutputOf(self):
    self.assertRaises(subprocess.CalledProcessError,
                      builder._OutputOf, ['/bin/false'])

    hello = 'hello, world'
    self.assertEqual(hello + '\n',
                     builder._OutputOf(['/bin/echo', hello]))


if __name__ == '__main__':
  unittest.main()
