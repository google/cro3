# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit test script for nginx_access_log_metrics."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest

import mock

import nginx_access_log_metrics


# pylint: disable=protected-access
class TestMetric(unittest.TestCase):
  """Test class for nginx_access_log_metrics."""

  def test_match_the_log_line(self):
    """Test the regex to match a target log line."""
    match = nginx_access_log_metrics._SUCCESS_RESPONSE_MATCHER.match(
        '100.109.169.118 2018-08-01T09:11:27-07:00 "GET a_url HTTP/1.1" '
        '200 12345 "agent/1.2.3" HIT')
    self.assertTrue(match)

    self.assertEqual(match.group('ip_addr'), '100.109.169.118')
    self.assertEqual(match.group('url_path'), 'a_url')
    self.assertEqual(match.group('size'), '12345')
    self.assertEqual(match.group('cache_status'), 'HIT')

  def test_match_URL_path(self):
    """Test the regex to match a URL path."""
    url = '/extract/a_bucket/a-release/R1-2.3/archive'
    # The match works for URL has or hasn't parameter.
    for u in [url, url + '?key=value']:
      match = nginx_access_log_metrics._URL_PATH_MATCHER.match(u)

      self.assertEqual(match.group('action'), 'extract')
      self.assertEqual(match.group('bucket'), 'a_bucket')
      self.assertEqual(match.group('build'), 'a-release')
      self.assertEqual(match.group('milestone'), 'R1')
      self.assertEqual(match.group('version'), '2.3')
      self.assertEqual(match.group('filename'), 'archive')

  def test_emitter(self):
    """Test the emitter."""
    match = nginx_access_log_metrics._SUCCESS_RESPONSE_MATCHER.match(
        '100.109.169.118 2018-08-01T09:11:27-07:00 "GET '
        '/extract/a_bucket/build/R1-2.3/archive HTTP/1.1" '
        '200 12345 "agent/1.2.3" HIT')
    # Calling the emitter should not raise any exceptions (for example, by
    # referencing regex match groups that don't exist.
    with mock.patch.object(nginx_access_log_metrics, 'metrics') as m:
      nginx_access_log_metrics.emit_successful_response_metric(match)
      m.Counter.assert_called_with(nginx_access_log_metrics._METRIC_NAME)
