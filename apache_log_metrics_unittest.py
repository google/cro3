#!/usr/bin/python2

# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for apache_log_metrics.py"""

from __future__ import print_function

import unittest

import apache_log_metrics


STATIC_REQUEST_LINE = (
    '172.24.26.30 - - [30/Jun/2016:15:34:40 -0700] '
    '"GET /static/veyron_minnie-release/R52-8350.46.0/'
    'autotest_server_package.tar.bz2'
    ' HTTP/1.1" 200 13805917 "-" "Wget/1.15    (linux-gnu)'
)


class TestParsers(unittest.TestCase):
  """Tests the parsing functions in apache_log_metrics."""

  def testParseStaticResponse(self):
    match = apache_log_metrics.STATIC_GET_MATCHER.match(
        STATIC_REQUEST_LINE)
    self.assertTrue(match)

    ip = match.group('ip_addr')
    self.assertEqual(ip, '172.24.26.30')
    self.assertFalse(apache_log_metrics.InLab(ip))

    self.assertEqual(match.group('size'), '13805917')


if __name__ == '__main__':
  unittest.main()
