#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for AppIndex class."""

from __future__ import print_function

import mock
import unittest

import nebraska
from unittest_common import AppDataGenerator

_NEBRASKA_PORT = 11235
_SOURCE_DIR = "test_source_dir"
_TARGET_DIR = "test_target_dir"

# pylint: disable=protected-access


class JSONStrings(object):
  """Collection of JSON strings for testing."""

  app_foo = """{
  "appid": "foo",
  "name": "foo",
  "is_delta": "false",
  "size": "9001",
  "hash_md5": "0xc0ffee",
  "metadata_sig": "0xdeadbeef",
  "metadata_size": "42",
  "hash_sha1": "0xl337c0de",
  "hash_sha256": "0xcafef00d",
  "version": "1.0.0",
  "source_ver": "null"
}
"""

  app_foo_update = """{
  "appid": "foo",
  "name": "foo",
  "is_delta": "true",
  "size": "9001",
  "hash_md5": "0xc0ffee",
  "metadata_sig": "0xdeadbeef",
  "metadata_size": "42",
  "hash_sha1": "0xl337c0de",
  "hash_sha256": "0xcafef00d",
  "version": "2.0.0",
  "source_ver": "1.0.0"
}
"""

  app_bar = """{
  "appid": "bar",
  "name": "bar",
  "is_delta": "false",
  "size": "9001",
  "hash_md5": "0xc0ffee",
  "metadata_sig": "0xdeadbeef",
  "metadata_size": "42",
  "hash_sha1": "0xl337c0de",
  "hash_sha256": "0xcafef00d",
  "version": "1.0.0",
  "source_ver": "null"
}
"""

  app_bar_update = """{
  "appid": "bar",
  "name": "bar",
  "is_delta": "true",
  "size": "9001",
  "hash_md5": "0xc0ffee",
  "metadata_sig": "0xdeadbeef",
  "metadata_size": "42",
  "hash_sha1": "0xl337c0de",
  "hash_sha256": "0xcafef00d",
  "version": "2.0.0",
  "source_ver": "1.0.0"
}
"""

  app_foobar = """{
  "appid": "foobar",
  "name": "foobar",
  "is_delta": "false",
  "size": "9001",
  "hash_md5": "0xc0ffee",
  "metadata_sig": "0xdeadbeef",
  "metadata_size": "42",
  "hash_sha1": "0xl337c0de",
  "hash_sha256": "0xcafef00d",
  "version": "1.0.0",
  "source_ver": "null"
}
"""

  invalid_app = """{
  "appid": "bar",
  "name": "bar",
  "size": "9001",
  "hash_md5": "0xc0ffee",
  "metadata_sig": "0xdeadbeef",
  "metadata_size": "42",
  "hash_sha1": "0xl337c0de",
  "hash_sha256": "0xcafef00d",
  "version": "1.0.0",
  "source_ver": "null"
}
"""

  invalid_json = """blah
{
  "appid": "bar",
  "name": "bar",
  "is_delta": "false",
  "size": "9001",
  "hash_md5": "0xc0ffee",
  "metadata_sig": "0xdeadbeef",
  "metadata_size": "42",
  "hash_sha1": "0xl337c0de",
  "hash_sha256": "0xcafef00d",
  "version": "1.0.0",
  "source_ver": "null"
}
"""


class AppIndexTest(unittest.TestCase):
  """Test AppIndex."""

  def testScanEmpty(self):
    """Tests Scan on an empty directory."""
    with mock.patch('nebraska.os.listdir') as listdir_mock:
      with mock.patch('nebraska.open') as open_mock:
        listdir_mock.return_value = []
        app_index = nebraska.AppIndex(_SOURCE_DIR)
        app_index.Scan()
        self.assertFalse(app_index._index)
        listdir_mock.assert_called_once_with(_SOURCE_DIR)
        open_mock.assert_not_called()

  def testScanNoJson(self):
    """Tests Scan on a directory with no JSON files."""
    with mock.patch('nebraska.os.listdir') as listdir_mock:
      with mock.patch('nebraska.open') as open_mock:
        listdir_mock.return_value = ["foo.bin", "bar.bin", "json"]
        app_index = nebraska.AppIndex(_SOURCE_DIR)
        app_index.Scan()
        self.assertFalse(app_index._index)
        listdir_mock.assert_called_once_with(_SOURCE_DIR)
        open_mock.assert_not_called()

  def testScanMultiple(self):
    """Tests Scan on a directory with multiple appids."""
    with mock.patch('nebraska.os.listdir') as listdir_mock:
      with mock.patch('nebraska.open') as open_mock:
        listdir_mock.return_value = [
            "foo_install.json",
            "foo_update.json",
            "bar_install.json",
            "bar_update.json",
            "foobar.json",
            "foobar.blah"
        ]

        open_mock.side_effect = [
            mock.mock_open(read_data=JSONStrings.app_foo).return_value,
            mock.mock_open(read_data=JSONStrings.app_foo_update).return_value,
            mock.mock_open(read_data=JSONStrings.app_bar).return_value,
            mock.mock_open(read_data=JSONStrings.app_bar_update).return_value,
            mock.mock_open(read_data=JSONStrings.app_foobar).return_value
        ]

        app_index = nebraska.AppIndex(_SOURCE_DIR)
        app_index.Scan()
        listdir_mock.assert_called_once_with(_SOURCE_DIR)
        self.assertTrue(set(app_index._index.keys()) ==
                        set(['foo', 'bar', 'foobar']))
        self.assertTrue(len(app_index._index['foo']) == 2)
        self.assertTrue(len(app_index._index['bar']) == 2)
        self.assertTrue(len(app_index._index['foobar']) == 1)

  def testScanInvalidJson(self):
    """Tests Scan with invalid JSON files."""
    with mock.patch('nebraska.os.listdir') as listdir_mock:
      with mock.patch('nebraska.open') as open_mock:
        listdir_mock.return_value = [
            "foo_install.json",
            "foo_update.json",
            "bar_install.json",
            "bar_update.json",
            "foobar.json",
            "foobar.blah"
        ]

        open_mock.side_effect = [
            mock.mock_open(read_data=JSONStrings.app_foo).return_value,
            mock.mock_open(read_data=JSONStrings.app_foo_update).return_value,
            IOError("File not found!"),
            mock.mock_open(read_data=JSONStrings.invalid_json).return_value,
            mock.mock_open(read_data=JSONStrings.app_foobar).return_value
        ]

        with self.assertRaises(IOError):
          app_index = nebraska.AppIndex(_SOURCE_DIR)
          app_index.Scan()

  def testScanInvalidApp(self):
    """Tests Scan on JSON files lacking required keys."""
    with mock.patch('nebraska.os.listdir') as listdir_mock:
      with mock.patch('nebraska.open') as open_mock:
        listdir_mock.return_value = [
            "foo_install.json",
            "foo_update.json",
            "bar_install.json",
            "bar_update.json",
            "foobar.json",
            "foobar.blah"
        ]

        open_mock.side_effect = [
            mock.mock_open(read_data=JSONStrings.app_foo).return_value,
            mock.mock_open(read_data=JSONStrings.app_foo_update).return_value,
            mock.mock_open(read_data=JSONStrings.invalid_app).return_value,
            mock.mock_open(read_data=JSONStrings.invalid_app).return_value,
            mock.mock_open(read_data=JSONStrings.app_foobar).return_value
        ]

        with self.assertRaises(KeyError):
          app_index = nebraska.AppIndex(_SOURCE_DIR)
          app_index.Scan()


class AppDataTest(unittest.TestCase):
  """Test AppData."""

  def testMatchRequestInstall(self):
    """Tests MatchRequest for matching install request."""
    app_data = AppDataGenerator(
        appid="foo",
        is_delta=False,
        version="1.2.0",
        src_version=None)
    request = nebraska.Request.AppRequest(
        request_type=nebraska.Request.AppRequest.RequestType.INSTALL,
        appid="foo",
        version="1.2.0")
    self.assertTrue(app_data.MatchRequest(request))

  def testMatchRequestDelta(self):
    """Tests MatchRequest for matching delta update request."""
    app_data = AppDataGenerator(
        appid="foo",
        is_delta=True,
        version="1.3.0",
        src_version="1.2.0")
    request = nebraska.Request.AppRequest(
        request_type=nebraska.Request.AppRequest.RequestType.UPDATE,
        appid="foo",
        version="1.2.0",
        delta_okay=True)
    self.assertTrue(app_data.MatchRequest(request))

  def testMatchRequestUpdate(self):
    """Tests MatchRequest for matching full update request."""
    app_data = AppDataGenerator(
        appid="foo",
        is_delta=False,
        version="1.3.0",
        src_version=None)
    request = nebraska.Request.AppRequest(
        request_type=nebraska.Request.AppRequest.RequestType.UPDATE,
        appid="foo",
        version="1.2.0",
        delta_okay=False)
    self.assertTrue(app_data.MatchRequest(request))

  def testMatchRequestAppidMismatch(self):
    """Tests MatchRequest for appid mismatch."""
    app_data = AppDataGenerator(
        appid="bar",
        is_delta=False,
        version="1.2.0",
        src_version=None)
    request = nebraska.Request.AppRequest(
        request_type=nebraska.Request.AppRequest.RequestType.INSTALL,
        appid="foo",
        version="1.2.0")
    self.assertFalse(app_data.MatchRequest(request))

  def testMatchRequestVersionMismatch(self):
    """Tests MatchRequest for install version mismatch."""

    app_data = AppDataGenerator(
        appid="foo",
        is_delta=False,
        version="2.2.0",
        src_version=None)
    request = nebraska.Request.AppRequest(
        request_type=nebraska.Request.AppRequest.RequestType.INSTALL,
        appid="foo",
        version="1.2.0")
    self.assertFalse(app_data.MatchRequest(request))

  def testMatchRequestDeltaVersionMismatch(self):
    """Test MatchRequest for delta version mismatch."""
    app_data = AppDataGenerator(
        appid="foo",
        is_delta=False,
        version="1.2.0",
        src_version="1.0.0")
    request = nebraska.Request.AppRequest(
        request_type=nebraska.Request.AppRequest.RequestType.UPDATE,
        appid="foo",
        version="1.2.0",
        delta_okay=True)
    self.assertFalse(app_data.MatchRequest(request))

  def testMatchRequestDeltaMismatch(self):
    """Tests MatchRequest for delta mismatch."""
    app_data = AppDataGenerator(
        appid="foo",
        is_delta=True,
        version="2.3.0",
        src_version="2.2.0")
    request = nebraska.Request.AppRequest(
        request_type=nebraska.Request.AppRequest.RequestType.UPDATE,
        appid="foo",
        version="2.2.0",
        delta_okay=False)
    self.assertFalse(app_data.MatchRequest(request))

    app_data = AppDataGenerator(
        appid="foo",
        is_delta=True,
        version="1.3.0",
        src_version="1.2.0")
    request = nebraska.Request.AppRequest(
        request_type=nebraska.Request.AppRequest.RequestType.INSTALL,
        appid="foo",
        version="1.3.0")
    self.assertFalse(app_data.MatchRequest(request))

  def testMatchRequestSourceMismatch(self):
    """Tests MatchRequest for delta source mismatch."""
    app_data = AppDataGenerator(
        appid="foo",
        is_delta=True,
        version="2.3.0",
        src_version="2.2.0")
    request = nebraska.Request.AppRequest(
        request_type=nebraska.Request.AppRequest.RequestType.UPDATE,
        appid="foo",
        version="1.2.0",
        delta_okay=True)
    self.assertFalse(app_data.MatchRequest(request))

  def testMatchRequestInvalidVersion(self):
    """Tests MatchRequest on invalid version string."""
    with mock.patch('nebraska.logging') as mock_log:
      app_data = AppDataGenerator(
          appid="foo",
          is_delta=True,
          version="2.3.0",
          src_version="2.2.0")
      request = nebraska.Request.AppRequest(
          request_type=nebraska.Request.AppRequest.RequestType.UPDATE,
          appid="foo",
          version="0xc0ffee",
          delta_okay=True)
      self.assertFalse(app_data.MatchRequest(request))
      mock_log.error.assert_called_once()

    with mock.patch('nebraska.logging') as mock_log:
      app_data = AppDataGenerator(
          appid="foo",
          is_delta=True,
          version="2,3,0",
          src_version="2.2.0")
      request = nebraska.Request.AppRequest(
          request_type=nebraska.Request.AppRequest.RequestType.UPDATE,
          appid="foo",
          version="2.2.0",
          delta_okay=True)
      self.assertFalse(app_data.MatchRequest(request))
      mock_log.error.assert_called_once()


if __name__ == '__main__':
  unittest.main()
