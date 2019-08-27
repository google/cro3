#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright (c) 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for cros_update_parser.py."""

from __future__ import print_function

import sys
import unittest

import cros_update

class CrosUpdateParserTest(unittest.TestCase):
  """Tests for the autoupdate.Autoupdate class."""

  def setUp(self):
    self.orig_sys_argv = sys.argv

  def tearDown(self):
    self.argv = self.orig_sys_argv

  def _get_parser(self):
    return cros_update.CrOSAUParser()

  def test_parse_args(self):
    host_name = '100.0.0.1'
    build_name = 'fake/image'
    sys.argv = ['run.py', '-d', host_name, '-b', build_name, '-q', 'test']
    parser = self._get_parser()
    parser.ParseArgs()
    self.assertEqual(host_name, parser.options.host_name)
    self.assertEqual(build_name, parser.options.build_name)
    self.assertEqual(['-q', 'test'], parser.removed_args)


if __name__ == '__main__':
  unittest.main()
