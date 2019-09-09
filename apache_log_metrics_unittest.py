#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for apache_log_metrics.py"""

from __future__ import print_function

import mock
import unittest

import apache_log_metrics


STATIC_REQUEST_LINE = (
    '172.24.26.30 - - [30/Jun/2016:15:34:40 -0700] '
    '"GET /static/veyron_minnie-release/R52-8350.46.0/'
    'autotest_server_package.tar.bz2'
    ' HTTP/1.1" 200 13805917 "-" "Wget/1.15    (linux-gnu)'
)

RPC_REQUEST_LINE = (
    '100.115.245.193 - - [08/Sep/2019:07:30:29 -0700] '
    '"GET /list_suite_controls?suite_name=cros_test_platform'
    '&build=candy-release/R78-12493.0.0 HTTP/1.1" 200 2724761 "-" "curl/7.35"',
    '100.115.196.119 - - [08/Sep/2019:07:14:38 -0700] '
    '"POST /update/nyan_big-release/R77-12371.46.0 HTTP/1.1" 200 416 "-" "-"',
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


class TestEmitters(unittest.TestCase):
  """Tests the emitter functions in apache_log_metrics."""

  def testEmitStaticResponse(self):
    match = apache_log_metrics.STATIC_GET_MATCHER.match(
        STATIC_REQUEST_LINE)
    # Calling the emitter should not raise any exceptions (for example, by
    # referencing regex match groups that don't exist.
    with mock.patch.object(apache_log_metrics, 'metrics'):
      apache_log_metrics.EmitStaticRequestMetric(match)

  def testEmitRpcUsageMetric(self):
    for line in RPC_REQUEST_LINE:
      match = apache_log_metrics.RPC_USAGE_MATCHER.match(line)
      with mock.patch.object(apache_log_metrics, 'metrics'):
        apache_log_metrics.EmitRpcUsageMetric(match)


if __name__ == '__main__':
  unittest.main()
