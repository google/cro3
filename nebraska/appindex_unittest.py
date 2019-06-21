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
import unittest_common

_NEBRASKA_PORT = 11235
_INSTALL_DIR = 'test_install_dir'
_UPDATE_DIR = 'test_update_dir'

# pylint: disable=protected-access


class JSONStrings(object):
  """Collection of JSON strings for testing."""

  app_foo = """{
  "appid": "foo",
  "is_delta": "false",
  "size": "9001",
  "metadata_signature": "0xdeadbeef",
  "metadata_size": "42",
  "sha256_hex": "0xcafef00d==",
  "target_version": "1.0.0",
  "source_version": "null"
}
"""

  app_foo_update = """{
  "appid": "foo",
  "is_delta": "true",
  "size": "9001",
  "metadata_signature": "0xdeadbeef",
  "metadata_size": "42",
  "sha256_hex": "0xcafef00d==",
  "target_version": "2.0.0",
  "source_version": "1.0.0"
}
"""

  app_bar = """{
  "appid": "bar",
  "is_delta": "false",
  "size": "9001",
  "metadata_signature": "0xdeadbeef",
  "metadata_size": "42",
  "sha256_hex": "0xcafef00d==",
  "target_version": "1.0.0",
  "source_version": "null"
}
"""

  app_bar_update = """{
  "appid": "bar",
  "is_delta": "true",
  "size": "9001",
  "metadata_signature": "0xdeadbeef",
  "metadata_size": "42",
  "sha256_hex": "0xcafef00d==",
  "target_version": "2.0.0",
  "source_version": "1.0.0"
}
"""

  app_foobar = """{
  "appid": "foobar",
  "is_delta": "false",
  "size": "9001",
  "metadata_signature": "0xdeadbeef",
  "metadata_size": "42",
  "sha256_hex": "0xcafef00d==",
  "target_version": "1.0.0",
  "source_version": "null"
}
"""

  app_empty = """{
  "appid": "",
  "is_delta": "false",
  "size": "9001",
  "metadata_signature": "0xdeadbeef",
  "metadata_size": "42",
  "sha256_hex": "0xcafef00d==",
  "target_version": "1.0.0",
  "source_version": "null"
}
"""

  invalid_app = """{
  "appid": "bar",
  "size": "9001",
  "metadata_signature": "0xdeadbeef",
  "metadata_size": "42",
  "sha256_hex": "0xcafef00d==",
  "target_version": "1.0.0",
  "source_version": "null"
}
"""

  invalid_json = """blah
{
  "appid": "bar",
  "is_delta": "false",
  "size": "9001",
  "metadata_signature": "0xdeadbeef",
  "metadata_size": "42",
  "sha256_hex": "0xcafef00d==",
  "target_version": "1.0.0",
  "source_version": "null"
}
"""


class AppIndexTest(unittest.TestCase):
  """Test AppIndex."""

  def testScanEmpty(self):
    """Tests Scan on an empty directory."""
    with mock.patch('nebraska.os.listdir') as listdir_mock:
      with mock.patch('nebraska.open') as open_mock:
        listdir_mock.return_value = []
        app_index = nebraska.AppIndex(_INSTALL_DIR)
        app_index.Scan()
        self.assertFalse(app_index._index)
        listdir_mock.assert_called_once_with(_INSTALL_DIR)
        open_mock.assert_not_called()

  def testScanNoJson(self):
    """Tests Scan on a directory with no JSON files."""
    with mock.patch('nebraska.os.listdir') as listdir_mock:
      with mock.patch('nebraska.open') as open_mock:
        listdir_mock.return_value = ['foo.bin', 'bar.bin', 'json']
        app_index = nebraska.AppIndex(_INSTALL_DIR)
        app_index.Scan()
        self.assertFalse(app_index._index)
        listdir_mock.assert_called_once_with(_INSTALL_DIR)
        open_mock.assert_not_called()

  def testScanMultiple(self):
    """Tests Scan on a directory with multiple appids."""
    # Providing some mock properties and non-properties files.
    with mock.patch('nebraska.os.listdir') as listdir_mock:
      with mock.patch('nebraska.open') as open_mock:
        listdir_mock.return_value = [
            'foo_install.json',
            'foo_update.json',
            'bar_install.json',
            'bar_update.json',
            'foobar.json',
            'foobar.blah'
        ]

        # Mock loading the properties files.
        open_mock.side_effect = [
            mock.mock_open(read_data=JSONStrings.app_foo).return_value,
            mock.mock_open(read_data=JSONStrings.app_foo_update).return_value,
            mock.mock_open(read_data=JSONStrings.app_bar).return_value,
            mock.mock_open(read_data=JSONStrings.app_bar_update).return_value,
            mock.mock_open(read_data=JSONStrings.app_foobar).return_value
        ]

        # Make sure the Scan() scans all the files and at least correct App IDs
        # are generated.
        app_index = nebraska.AppIndex(_INSTALL_DIR)
        app_index.Scan()
        listdir_mock.assert_called_once_with(_INSTALL_DIR)
        self.assertEqual(
            [x.appid for x in app_index._index],
            ['foo', 'foo', 'bar', 'bar', 'foobar'])

  def testScanInvalidJson(self):
    """Tests Scan with invalid JSON files."""
    # Providing some mock properties and non-properties files.
    with mock.patch('nebraska.os.listdir') as listdir_mock:
      with mock.patch('nebraska.open') as open_mock:
        listdir_mock.return_value = [
            'foo_install.json',
            'foo_update.json',
            'bar_install.json',
            'bar_update.json',
            'foobar.json',
            'foobar.blah'
        ]

        # Mock loading the properties files.
        open_mock.side_effect = [
            mock.mock_open(read_data=JSONStrings.app_foo).return_value,
            mock.mock_open(read_data=JSONStrings.app_foo_update).return_value,
            IOError('File not found!'),
            mock.mock_open(read_data=JSONStrings.invalid_json).return_value,
            mock.mock_open(read_data=JSONStrings.app_foobar).return_value
        ]

        # Make sure we raise error when loading files raises one.
        with self.assertRaises(IOError):
          app_index = nebraska.AppIndex(_INSTALL_DIR)
          app_index.Scan()

  def testScanInvalidApp(self):
    """Tests Scan on JSON files lacking required keys."""
    # Providing some mock properties and non-properties files.
    with mock.patch('nebraska.os.listdir') as listdir_mock:
      with mock.patch('nebraska.open') as open_mock:
        listdir_mock.return_value = [
            'foo_install.json',
            'foo_update.json',
            'bar_install.json',
            'bar_update.json',
            'foobar.json',
            'foobar.blah'
        ]

        # Mock loading the properties files.
        open_mock.side_effect = [
            mock.mock_open(read_data=JSONStrings.app_foo).return_value,
            mock.mock_open(read_data=JSONStrings.app_foo_update).return_value,
            mock.mock_open(read_data=JSONStrings.invalid_app).return_value,
            mock.mock_open(read_data=JSONStrings.invalid_app).return_value,
            mock.mock_open(read_data=JSONStrings.app_foobar).return_value
        ]

        # Make sure we raise error when properties files are invalid.
        with self.assertRaises(KeyError):
          app_index = nebraska.AppIndex(_INSTALL_DIR)
          app_index.Scan()

  def testContains(self):
    """Tests Constains() correctly finds matching AppData."""
    # Providing some mock properties files.
    with mock.patch('nebraska.os.listdir') as listdir_mock:
      with mock.patch('nebraska.open') as open_mock:
        listdir_mock.return_value = [
            'foo.json',
        ]
        # Mock loading the properties files.
        open_mock.side_effect = [
            mock.mock_open(read_data=JSONStrings.app_foo).return_value,
            mock.mock_open(read_data=JSONStrings.app_empty).return_value,
        ]

        app_index = nebraska.AppIndex(_UPDATE_DIR)
        app_index.Scan()

        no_match_request = unittest_common.GenerateAppRequest(appid='random')
        self.assertFalse(app_index.Contains(no_match_request))

        # Matches against the AppData with exact appid 'foo'.
        match_request = unittest_common.GenerateAppRequest(appid='foo')
        self.assertTrue(app_index.Contains(match_request))

        # Partially matches against the AppData with appid 'foo'.
        partial_match_request = unittest_common.GenerateAppRequest(
            appid='mefoolme')
        self.assertTrue(app_index.Contains(partial_match_request))

  def testContainsEmpty(self):
    """Tests Constains() correctly finds matching AppData with empty appid."""
    # Providing some mock properties files.
    with mock.patch('nebraska.os.listdir') as listdir_mock:
      with mock.patch('nebraska.open') as open_mock:
        listdir_mock.return_value = [
            'foo.json',
            'empty.json'
        ]
        # Mock loading the properties files.
        open_mock.side_effect = [
            mock.mock_open(read_data=JSONStrings.app_foo).return_value,
            mock.mock_open(read_data=JSONStrings.app_empty).return_value,
        ]

        app_index = nebraska.AppIndex(_UPDATE_DIR)
        app_index.Scan()

        request = unittest_common.GenerateAppRequest(appid='random')
        # It will match against the AppData with an empty appid.
        self.assertTrue(app_index.Contains(request))

class AppDataTest(unittest.TestCase):
  """Test AppData."""

  def testMatchAppDataInstall(self):
    """Tests MatchAppData for matching install request."""
    app_data = unittest_common.GenerateAppData(source_version=None)
    request = unittest_common.GenerateAppRequest(
        request_type=nebraska.Request.RequestType.INSTALL)
    self.assertTrue(request.MatchAppData(app_data))

  def testMatchAppDataDelta(self):
    """Tests MatchAppData for matching delta update request."""
    app_data = unittest_common.GenerateAppData(is_delta=True,
                                               source_version='1.0.0')
    request = unittest_common.GenerateAppRequest(delta_okay=True)
    self.assertTrue(request.MatchAppData(app_data))

  def testMatchAppDataUpdate(self):
    """Tests MatchAppData for matching full update request."""
    app_data = unittest_common.GenerateAppData()
    request = unittest_common.GenerateAppRequest()
    self.assertTrue(request.MatchAppData(app_data))

  def testMatchAppDataAppidMismatch(self):
    """Tests MatchAppData for appid mismatch."""
    app_data = unittest_common.GenerateAppData(appid='bar')
    request = unittest_common.GenerateAppRequest(
        appid='foo',
        request_type=nebraska.Request.RequestType.INSTALL)
    self.assertFalse(request.MatchAppData(app_data))

  def testMatchAppDataDeltaMismatch(self):
    """Tests MatchAppData for delta mismatch."""
    app_data = unittest_common.GenerateAppData(is_delta=True,
                                               source_version='1.2.0')
    request = unittest_common.GenerateAppRequest(delta_okay=False)
    self.assertFalse(request.MatchAppData(app_data))

    app_data = unittest_common.GenerateAppData(is_delta=True,
                                               source_version='1.2.0')
    request = unittest_common.GenerateAppRequest(
        request_type=nebraska.Request.RequestType.INSTALL,
        delta_okay=True)
    self.assertFalse(request.MatchAppData(app_data))

  def testMatchAppDataWildCardMatchingEmptyAppId(self):
    """Tests MatchAppData for matching update request with empty appid."""
    app_data = unittest_common.GenerateAppData(appid='')
    request = unittest_common.GenerateAppRequest(appid='foobar')
    self.assertFalse(request.MatchAppData(app_data))
    self.assertTrue(request.MatchAppData(app_data, partial_match_appid=True))

  def testMatchAppDataWildCardMatchingPartialAppId(self):
    """Tests MatchAppData for matching update request with partial appid."""
    app_data = unittest_common.GenerateAppData(appid='oob')
    request = unittest_common.GenerateAppRequest(appid='foobar')
    self.assertFalse(request.MatchAppData(app_data))
    self.assertTrue(request.MatchAppData(app_data, partial_match_appid=True))

  def testNoMatchAppDataWildCardMatchingPartialAppId(self):
    """Tests MatchAppData for not matching update request with partial appid."""
    app_data = unittest_common.GenerateAppData(appid='foo')
    request = unittest_common.GenerateAppRequest(appid='bar')
    self.assertFalse(request.MatchAppData(app_data))
    self.assertFalse(request.MatchAppData(app_data, partial_match_appid=True))

if __name__ == '__main__':
  unittest.main()
