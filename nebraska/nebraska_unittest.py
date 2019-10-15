#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittests for Nebraska server."""

from __future__ import print_function

# pylint: disable=cros-logging-import
import logging
import os
import shutil
import tempfile
import unittest

from xml.etree import ElementTree
import mock

from six.moves import builtins
from six.moves import http_client

import nebraska

_NEBRASKA_PORT = 11235
_INSTALL_DIR = 'test_install_dir'
_UPDATE_DIR = 'test_update_dir'
_PAYLOAD_ADDRESS = '111.222.212:2357'
_UPDATE_PAYLOADS_ADDRESS = 'www.google.com/update'
_INSTALL_PAYLOADS_ADDRESS = 'www.google.com/install'

# pylint: disable=protected-access

def GenerateAppData(appid='foo', name='foobar', is_delta=False,
                    target_version='2.0.0', source_version=None,
                    include_public_key=False):
  """Generates an AppData test instance."""
  data = {
      nebraska.AppIndex.AppData.APPID_KEY: appid,
      nebraska.AppIndex.AppData.NAME_KEY: name,
      nebraska.AppIndex.AppData.TARGET_VERSION_KEY: target_version,
      nebraska.AppIndex.AppData.IS_DELTA_KEY: is_delta,
      nebraska.AppIndex.AppData.SOURCE_VERSION_KEY: source_version,
      nebraska.AppIndex.AppData.SIZE_KEY: '9001',
      nebraska.AppIndex.AppData.METADATA_SIG_KEY: \
          'Dr4RFXYgcfvFHV/0VRQs+SCQmz15Sk04LLEDswtvng8BqNbBXA7VvPUhpCgX5T/t7cwP'
          'xTUHJVtxIREuBZpyIQxJQFZATspaClelpKBwadQzj7dpfShLpcbdlfM8qbLjIbXfC2Vy'
          'mw03Mwf38lm0Fm75SANSTW9S4arPDf3sy9YGuqesnEJXyT3ZSGyK+Xto79zlURUXCgmi'
          'a6t7MaJE3ZbCdeF4EiEMPDsipqj9ggmKwiCdUl2+RxTznX/015XFiBhogLrx9RCPHTR8'
          'nLz0H9RcRhIvMd+8g4kHUZTDvjCvG5EZHpIKk8FK8z0zY/LWVr738evwuNNwyKIazkQB'
          'TA==',
      nebraska.AppIndex.AppData.METADATA_SIZE_KEY: '42',
      nebraska.AppIndex.AppData.SHA256_HEX_KEY: \
          '886fd274745b4fa8d1f253cff11242fac07a29522b1bb9e028ab1480353d3160'
  }
  if include_public_key:
    data[nebraska.AppIndex.AppData.PUBLIC_KEY_RSA_KEY] = 'foo-public-key'
  return nebraska.AppIndex.AppData(data)

def GenerateAppRequest(request_type=nebraska.Request.RequestType.UPDATE,
                       appid='foo', version='1.0.0', delta_okay=False,
                       event=False, event_type='1', event_result='1',
                       update_check=True, ping=False):
  """Generates an app request test instance."""
  APP_TEMPLATE = """<app appid="" version="" delta_okay=""
track="foo-channel" board="foo-board"> </app>"""
  PING_TEMPLATE = """<ping active="1" a="1" r="1"></ping>"""
  UPDATE_CHECK_TEMPLATE = """<updatecheck></updatecheck>"""
  EVENT_TEMPLATE = """<event eventtype="3" eventresult="1"></event>"""

  app = ElementTree.fromstring(APP_TEMPLATE)
  app.set('appid', appid)
  app.set('version', version)
  app.set('delta_okay', 'true' if delta_okay else 'false')

  if ping:
    app.append(ElementTree.fromstring(PING_TEMPLATE))
  if update_check:
    app.append(ElementTree.fromstring(UPDATE_CHECK_TEMPLATE))
  if event:
    event_tag = ElementTree.fromstring(EVENT_TEMPLATE)
    event_tag.set('eventtype', event_type)
    event_tag.set('eventresult', event_result)
    app.append(event_tag)

  return nebraska.Request.AppRequest(app, request_type)

class NebraskaUnitTest(unittest.TestCase):
  """Parent class for all unit test classes here."""


class MockNebraskaHandler(nebraska.NebraskaServer.NebraskaHandler):
  """Subclass NebraskaHandler to facilitate testing.

  Because of the complexity of the socket handling super class init functions,
  the easiest way to test NebraskaHandler is to just subclass it and mock
  whatever we need from its super classes.
  """
  # pylint: disable=super-init-not-called
  def __init__(self):
    self.headers = mock.MagicMock()
    self.path = mock.MagicMock()
    self._SendResponse = mock.MagicMock()
    self.send_error = mock.MagicMock()
    self.rfile = mock.MagicMock()
    self.server = mock.MagicMock()
    self.server.owner = nebraska.NebraskaServer(nebraska.Nebraska(
        _PAYLOAD_ADDRESS, _PAYLOAD_ADDRESS))


class NebraskaTest(NebraskaUnitTest):
  """Test Nebraska."""

  def testDefaultInstallPayloadsAddress(self):
    """Tests the default install_payloads_address is correctly set."""
    update_addr = 'foo/update/'
    install_addr = 'foo/install/'
    # pylint: disable=protected-access
    n = nebraska.Nebraska(update_addr, install_addr)
    self.assertEqual(n._properties.install_payloads_address, install_addr)
    self.assertEqual(n._properties.update_payloads_address, update_addr)

    n = nebraska.Nebraska(update_addr)
    self.assertEqual(n._properties.install_payloads_address, update_addr)

    n = nebraska.Nebraska()
    self.assertEqual(n._properties.update_payloads_address, '')
    self.assertEqual(n._properties.install_payloads_address, '')

class NebraskaHandlerTest(NebraskaUnitTest):
  """Test NebraskaHandler."""

  def testParseURL(self):
    """Tests _ParseURL with different URLs."""
    nebraska_handler = MockNebraskaHandler()
    self.assertEqual(
        nebraska_handler._ParseURL('http://goo.gle/path/?tick=tock'),
        ('path', {'tick': ['tock']}))

    self.assertEqual(nebraska_handler._ParseURL('http://goo.gle/path/'),
                     ('path', {}))

    self.assertEqual(nebraska_handler._ParseURL('http://goo.gle/'), ('', {}))

  def testDoPostSuccess(self):
    """Tests do_POST success."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/update'
    test_response = 'foobar'

    with mock.patch.object(nebraska.Nebraska,
                           'GetResponseToRequest') as response_mock:
      with mock.patch.object(nebraska, 'Request'):
        response_mock.return_value = test_response
        nebraska_handler.do_POST()

        response_mock.assert_called_once_with(mock.ANY, critical_update=False,
                                              no_update=False)
        nebraska_handler._SendResponse.assert_called_once_with(
            'application/xml', test_response)

  def testDoPostSuccessWithCriticalUpdate(self):
    """Tests do_POST success with critical_update query string in URL."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/update/?critical_update=True'

    with mock.patch.object(nebraska.Nebraska,
                           'GetResponseToRequest') as response_mock:
      with mock.patch.object(nebraska, 'Request'):
        nebraska_handler.do_POST()

        response_mock.assert_called_once_with(mock.ANY, critical_update=True,
                                              no_update=False)

  def testDoPostSuccessWithNoUpdate(self):
    """Tests do_POST success with no_update query string in URL."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/update/?no_update=True'

    with mock.patch.object(nebraska.Nebraska,
                           'GetResponseToRequest') as response_mock:
      with mock.patch.object(nebraska, 'Request'):
        nebraska_handler.do_POST()

        response_mock.assert_called_once_with(mock.ANY, critical_update=False,
                                              no_update=True)

  def testDoPostInvalidPath(self):
    """Test do_POST invalid path."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/invalid-path'

    nebraska_handler.do_POST()

    nebraska_handler.send_error.assert_called_once_with(
        http_client.BAD_REQUEST,
        'The requested path "invalid-path" was not found!')

  def testDoPostInvalidRequest(self):
    """Test do_POST invalid request."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/update'

    with mock.patch.object(nebraska, 'traceback') as traceback_mock:
      with mock.patch.object(nebraska.Request, 'ParseRequest') as parse_mock:
        parse_mock.side_effect = nebraska.NebraskaErrorInvalidRequest
        nebraska_handler.do_POST()

        self.assertEqual(traceback_mock.format_exc.call_count, 2)
        nebraska_handler.send_error.assert_called_once_with(
            http_client.INTERNAL_SERVER_ERROR, traceback_mock.format_exc())

  def testDoPostInvalidResponse(self):
    """Tests do_POST invalid response handling."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/update'

    with mock.patch.object(nebraska, 'traceback') as traceback_mock:
      with mock.patch.object(nebraska, 'Response') as response_mock:
        response_instance = response_mock.return_value
        response_instance.GetXMLString.side_effect = Exception
        nebraska_handler.do_POST()

        self.assertEqual(traceback_mock.format_exc.call_count, 2)
        nebraska_handler.send_error.assert_called_once_with(
            http_client.INTERNAL_SERVER_ERROR, traceback_mock.format_exc())

  def testDoGetSuccess(self):
    """Tests do_GET success."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/requestlog'

    nebraska_handler.do_GET()
    nebraska_handler._SendResponse.assert_called_once_with(
        'application/json', '[]')

  def testDoGetFailureBadPath(self):
    """Tests do_GET failure on bad path."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/invalid-path'

    nebraska_handler.do_GET()
    nebraska_handler.send_error(http_client.BAD_REQUEST, mock.ANY)

class NebraskaServerTest(NebraskaUnitTest):
  """Test NebraskaServer."""

  def testStart(self):
    """Tests Start."""
    nebraska_instance = nebraska.Nebraska(_PAYLOAD_ADDRESS, _PAYLOAD_ADDRESS)
    server = nebraska.NebraskaServer(nebraska_instance, port=_NEBRASKA_PORT)

    with mock.patch.object(nebraska.BaseHTTPServer,
                           'HTTPServer') as server_mock:
      with mock.patch.object(nebraska.threading, 'Thread') as thread_mock:
        server.Start()

        server_mock.assert_called_once_with(
            ('', _NEBRASKA_PORT), nebraska.NebraskaServer.NebraskaHandler)

        # pylint: disable=protected-access
        thread_mock.assert_has_calls([
            mock.call(target=server._httpd.serve_forever),
            mock.call().start()])

  def testStop(self):
    """Tests Stop."""
    nebraska_instance = nebraska.Nebraska(_PAYLOAD_ADDRESS, _PAYLOAD_ADDRESS)
    server = nebraska.NebraskaServer(nebraska_instance, port=_NEBRASKA_PORT)

    # pylint: disable=protected-access
    server._httpd = mock.MagicMock(name='_httpd')
    server._server_thread = mock.MagicMock(name='_server_thread')
    server.Stop()
    # pylint: disable=protected-access
    server._httpd.shutdown.assert_called_once_with()
    server._server_thread.join.assert_called_once_with()

  def testMiscFiles(self):
    """Tests PID and port files are correctly written."""
    temp_dir = tempfile.mkdtemp()
    runtime_root = os.path.join(temp_dir, 'runtime_root')
    nebraska_instance = nebraska.Nebraska(_PAYLOAD_ADDRESS, _PAYLOAD_ADDRESS)
    server = nebraska.NebraskaServer(nebraska_instance, port=_NEBRASKA_PORT,
                                     runtime_root=runtime_root)

    port_file = os.path.join(runtime_root, 'port')
    pid_file = os.path.join(runtime_root, 'pid')

    with mock.patch.object(nebraska.BaseHTTPServer, 'HTTPServer'):
      with mock.patch.object(nebraska.threading, 'Thread'):
        server.Start()

        # Make sure files are created and written with correct values.
        with open(port_file, 'r') as f:
          self.assertEqual(f.read(), str(server.GetPort()))
        with open(pid_file, 'r') as f:
          self.assertEqual(f.read(), str(os.getpid()))

        server.Stop()

        # Make sure files are deleted correctly.
        self.assertFalse(os.path.exists(runtime_root))

    # Delete the temp directory.
    shutil.rmtree(temp_dir, ignore_errors=True)


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

class AppIndexTest(NebraskaUnitTest):
  """Test AppIndex."""

  def testScanEmpty(self):
    """Tests Scan on an empty directory."""
    with mock.patch('os.listdir') as listdir_mock:
      with mock.patch.object(builtins, 'open') as open_mock:
        listdir_mock.return_value = []
        app_index = nebraska.AppIndex(_INSTALL_DIR)
        app_index.Scan()
        self.assertFalse(app_index._index)
        listdir_mock.assert_called_once_with(_INSTALL_DIR)
        open_mock.assert_not_called()

  def testScanNoJson(self):
    """Tests Scan on a directory with no JSON files."""
    with mock.patch('os.listdir') as listdir_mock:
      with mock.patch.object(builtins, 'open') as open_mock:
        listdir_mock.return_value = ['foo.bin', 'bar.bin', 'json']
        app_index = nebraska.AppIndex(_INSTALL_DIR)
        app_index.Scan()
        self.assertFalse(app_index._index)
        listdir_mock.assert_called_once_with(_INSTALL_DIR)
        open_mock.assert_not_called()

  def testScanMultiple(self):
    """Tests Scan on a directory with multiple appids."""
    # Providing some mock properties and non-properties files.
    with mock.patch('os.listdir') as listdir_mock:
      with mock.patch.object(builtins, 'open') as open_mock:
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
    with mock.patch('os.listdir') as listdir_mock:
      with mock.patch.object(builtins, 'open') as open_mock:
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
    with mock.patch('os.listdir') as listdir_mock:
      with mock.patch.object(builtins, 'open') as open_mock:
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
    with mock.patch('os.listdir') as listdir_mock:
      with mock.patch.object(builtins, 'open') as open_mock:
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

        no_match_request = GenerateAppRequest(appid='random')
        self.assertFalse(app_index.Contains(no_match_request))

        # Matches against the AppData with exact appid 'foo'.
        match_request = GenerateAppRequest(appid='foo')
        self.assertTrue(app_index.Contains(match_request))

        # Partially matches against the AppData with appid 'foo'.
        partial_match_request = GenerateAppRequest(
            appid='mefoolme')
        self.assertTrue(app_index.Contains(partial_match_request))

  def testContainsEmpty(self):
    """Tests Constains() correctly finds matching AppData with empty appid."""
    # Providing some mock properties files.
    with mock.patch('os.listdir') as listdir_mock:
      with mock.patch.object(builtins, 'open') as open_mock:
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

        request = GenerateAppRequest(appid='random')
        # It will match against the AppData with an empty appid.
        self.assertTrue(app_index.Contains(request))

class AppDataTest(NebraskaUnitTest):
  """Test AppData."""

  def testMatchAppDataInstall(self):
    """Tests MatchAppData for matching install request."""
    app_data = GenerateAppData(source_version=None)
    request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.INSTALL)
    self.assertTrue(request.MatchAppData(app_data))

  def testMatchAppDataDelta(self):
    """Tests MatchAppData for matching delta update request."""
    app_data = GenerateAppData(is_delta=True, source_version='1.0.0')
    request = GenerateAppRequest(delta_okay=True)
    self.assertTrue(request.MatchAppData(app_data))

  def testMatchAppDataUpdate(self):
    """Tests MatchAppData for matching full update request."""
    app_data = GenerateAppData()
    request = GenerateAppRequest()
    self.assertTrue(request.MatchAppData(app_data))

  def testMatchAppDataAppidMismatch(self):
    """Tests MatchAppData for appid mismatch."""
    app_data = GenerateAppData(appid='bar')
    request = GenerateAppRequest(
        appid='foo',
        request_type=nebraska.Request.RequestType.INSTALL)
    self.assertFalse(request.MatchAppData(app_data))

  def testMatchAppDataDeltaMismatch(self):
    """Tests MatchAppData for delta mismatch."""
    app_data = GenerateAppData(is_delta=True, source_version='1.2.0')
    request = GenerateAppRequest(delta_okay=False)
    self.assertFalse(request.MatchAppData(app_data))

    app_data = GenerateAppData(is_delta=True, source_version='1.2.0')
    request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.INSTALL, delta_okay=True)
    self.assertFalse(request.MatchAppData(app_data))

  def testMatchAppDataWildCardMatchingEmptyAppId(self):
    """Tests MatchAppData for matching update request with empty appid."""
    app_data = GenerateAppData(appid='')
    request = GenerateAppRequest(appid='foobar')
    self.assertFalse(request.MatchAppData(app_data))
    self.assertTrue(request.MatchAppData(app_data, partial_match_appid=True))

  def testMatchAppDataWildCardMatchingPartialAppId(self):
    """Tests MatchAppData for matching update request with partial appid."""
    app_data = GenerateAppData(appid='oob')
    request = GenerateAppRequest(appid='foobar')
    self.assertFalse(request.MatchAppData(app_data))
    self.assertTrue(request.MatchAppData(app_data, partial_match_appid=True))

  def testNoMatchAppDataWildCardMatchingPartialAppId(self):
    """Tests MatchAppData for not matching update request with partial appid."""
    app_data = GenerateAppData(appid='foo')
    request = GenerateAppRequest(appid='bar')
    self.assertFalse(request.MatchAppData(app_data))
    self.assertFalse(request.MatchAppData(app_data, partial_match_appid=True))

class XMLStrings(object):
  """Collection of XML request strings for testing."""

  INSTALL_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" delta_okay="false"
       track="stable-channel" board="eve">
    <ping active="1" a="1" r="1"></ping>
  </app>
  <app appid="foo" version="1.0.0" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
  <app appid="bar" version="1.0.0" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
</request>
"""

  UPDATE_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" delta_okay="true"
       track="stable-channel" board="eve">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
  <app appid="foo" version="1.0.0" delta_okay="true">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
    <event eventtype="3" eventresult="1" previousversion="1"></event>
  </app>
  <app appid="bar" version="1.0.0" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
</request>
"""

  INVALID_NOOP_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" delta_okay="true"
       track="stable-channel" board="eve">
    <ping active="1" a="1" r="1"></ping>
  </app>
  <app appid="foo" version="1.0.0" delta_okay="true">
    <ping active="1" a="1" r="1"></ping>
  </app>
  <app appid="bar" version="1.0.0" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
</request>
"""

  EVENT_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" delta_okay="true"
       track="stable-channel" board="eve">
    <event eventtype="3" eventresult="1" previousversion="1"></event>
  </app>
</request>
"""

  INVALID_XML_REQUEST = """invalid xml!
<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="foo" version="1.0.0" delta_okay="false" track="stable-channel"
       board="eve">
    <ping active="1" a="1" r="1"></ping>
  </app>
</request>
"""

  # No appid.
  INVALID_APP_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app version="1.0.0" delta_okay="true"
       track="stable-channel" board="eve">
    <ping active="1" a="1" r="1"></ping>
  </app>
</request>
"""

  # No version number.
  INVALID_INSTALL_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" delta_okay="false"
       track="stable-channel" board="eve">
    <ping active="1" a="1" r="1"></ping>
  </app>
  <app appid="foo" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
</request>
"""

  # Missing all board attributes.
  MISSING_REQUIRED_ATTR_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
  </app>
  <app appid="foo" version="1.0.0" track="stable-channel" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
</request>
"""

  # Mismatched versions.
  MISMATCHED_VERSION_ATTR_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" delta_okay="false"
       track="stable-channel" board="eve">
    <ping active="1" a="1" r="1"></ping>
  </app>
  <app appid="foo" version="2.0.0" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
</request>
"""

class RequestTest(NebraskaUnitTest):
  """Tests for Request class."""

  def testParseRequestInvalidXML(self):
    """Tests ParseRequest handling of invalid XML."""
    with self.assertRaises(nebraska.NebraskaErrorInvalidRequest):
      nebraska.Request(XMLStrings.INVALID_XML_REQUEST)

  def testParseRequestInvalidApp(self):
    """Tests ParseRequest handling of invalid app requests."""
    with self.assertRaises(nebraska.NebraskaErrorInvalidRequest):
      nebraska.Request(XMLStrings.INVALID_APP_REQUEST)

  def testParseRequestInvalidInstall(self):
    """Tests ParseRequest handling of invalid app requests."""
    with self.assertRaises(nebraska.NebraskaErrorInvalidRequest):
      nebraska.Request(XMLStrings.INVALID_INSTALL_REQUEST)

  def testParseRequestInvalidNoop(self):
    """Tests ParseRequest handling of invalid mixed no-op request."""
    with self.assertRaises(nebraska.NebraskaErrorInvalidRequest):
      nebraska.Request(XMLStrings.INVALID_NOOP_REQUEST)

  def testParseRequestMissingAtLeastOneRequiredAttr(self):
    """Tests ParseRequest handling of missing required attributes in request."""
    with self.assertRaises(nebraska.NebraskaErrorInvalidRequest):
      nebraska.Request(XMLStrings.MISSING_REQUIRED_ATTR_REQUEST)

  def testParseRequestMismatchedVersion(self):
    """Tests ParseRequest handling of mismatched version numbers."""
    with self.assertRaises(nebraska.NebraskaErrorInvalidRequest):
      nebraska.Request(XMLStrings.MISMATCHED_VERSION_ATTR_REQUEST)

  def testParseRequestInstall(self):
    """Tests ParseRequest handling of install requests."""
    app_requests = nebraska.Request(XMLStrings.INSTALL_REQUEST).app_requests

    self.assertTrue(app_requests[0].request_type ==
                    nebraska.Request.RequestType.INSTALL)
    self.assertTrue(app_requests[1].request_type ==
                    nebraska.Request.RequestType.INSTALL)
    self.assertTrue(app_requests[2].request_type ==
                    nebraska.Request.RequestType.INSTALL)

    self.assertTrue(app_requests[0].appid == 'platform')
    self.assertTrue(app_requests[1].appid == 'foo')
    self.assertTrue(app_requests[2].appid == 'bar')

    self.assertTrue(app_requests[0].version == '1.0.0')
    self.assertTrue(app_requests[1].version == '1.0.0')
    self.assertTrue(app_requests[2].version == '1.0.0')

  def testParseRequestUpdate(self):
    """Tests ParseRequest handling of update requests."""
    app_requests = nebraska.Request(XMLStrings.UPDATE_REQUEST).app_requests

    self.assertTrue(app_requests[0].request_type ==
                    nebraska.Request.RequestType.UPDATE)
    self.assertTrue(app_requests[1].request_type ==
                    nebraska.Request.RequestType.UPDATE)
    self.assertTrue(app_requests[2].request_type ==
                    nebraska.Request.RequestType.UPDATE)

    self.assertTrue(app_requests[0].appid == 'platform')
    self.assertTrue(app_requests[1].appid == 'foo')
    self.assertTrue(app_requests[2].appid == 'bar')

    self.assertTrue(app_requests[0].version == '1.0.0')
    self.assertTrue(app_requests[1].version == '1.0.0')
    self.assertTrue(app_requests[2].version == '1.0.0')

    self.assertTrue(app_requests[0].delta_okay)
    self.assertTrue(app_requests[1].delta_okay)
    self.assertFalse(app_requests[2].delta_okay)

  def testParseRequestEventPing(self):
    """Tests ParseRequest handling of event ping requests."""
    app_requests = nebraska.Request(XMLStrings.EVENT_REQUEST).app_requests

    self.assertTrue(app_requests[0].request_type ==
                    nebraska.Request.RequestType.EVENT)
    self.assertTrue(app_requests[0].appid == 'platform')
    self.assertTrue(app_requests[0].event_type == 3)
    self.assertTrue(app_requests[0].event_result == 1)
    self.assertTrue(app_requests[0].previous_version == '1')

class ResponseTest(NebraskaUnitTest):
  """Tests for Response class."""

  def testGetXMLStringSuccess(self):
    """Tests GetXMLString success."""
    properties = nebraska.NebraskaProperties(
        _UPDATE_PAYLOADS_ADDRESS,
        _INSTALL_PAYLOADS_ADDRESS,
        nebraska.AppIndex(mock.MagicMock()),
        nebraska.AppIndex(mock.MagicMock()))

    app_list = (
        GenerateAppData(is_delta=True, source_version='0.9.0'),
        GenerateAppData(appid='bar', is_delta=True, source_version='1.9.0'),
        GenerateAppData(appid='foobar'))
    properties.update_app_index._index = app_list

    request = mock.MagicMock()
    request.app_requests = [
        GenerateAppRequest(
            request_type=nebraska.Request.RequestType.UPDATE,
            appid='foo',
            ping=True,
            delta_okay=False),
        GenerateAppRequest(
            request_type=nebraska.Request.RequestType.UPDATE,
            appid='bar',
            ping=True,
            delta_okay=False),
        GenerateAppRequest(
            request_type=nebraska.Request.RequestType.UPDATE,
            appid='foobar',
            ping=True,
            delta_okay=False)]

    response = nebraska.Response(request, properties).GetXMLString()
    response_root = ElementTree.fromstring(response)
    app_responses = response_root.findall('app')

    self.assertTrue(len(app_responses), 3)
    for response, app in zip(app_responses, app_list):
      self.assertTrue(response.attrib['appid'] == app.appid)
      self.assertTrue(response.find('ping') is not None)


class AppResponseTest(NebraskaUnitTest):
  """Tests for AppResponse class."""

  def setUp(self):
    """Setting up common parameters."""
    self._properties = nebraska.NebraskaProperties(
        _UPDATE_PAYLOADS_ADDRESS,
        _INSTALL_PAYLOADS_ADDRESS,
        mock.MagicMock(),
        mock.MagicMock())

  def testAppResponseUpdate(self):
    """Tests AppResponse for an update request with matching payload."""
    app_request = GenerateAppRequest()
    match = GenerateAppData()
    self._properties.update_app_index.Find.return_value = match

    response = nebraska.Response.AppResponse(app_request, self._properties)

    self.assertTrue(_UPDATE_PAYLOADS_ADDRESS in
                    ElementTree.tostring(response.Compile()))
    self.assertTrue(response._app_request == app_request)
    self.assertFalse(response._err_not_found)
    self.assertTrue(response._app_data is match)

    self._properties.update_app_index.Find.assert_called_once_with(app_request)
    self._properties.install_app_index.Find.assert_not_called()

  def testAppResponseInstall(self):
    """Tests AppResponse generation for install request with match."""
    app_request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.INSTALL)
    match = GenerateAppData()
    self._properties.install_app_index.Find.return_value = match

    response = nebraska.Response.AppResponse(app_request, self._properties)

    self.assertTrue(_INSTALL_PAYLOADS_ADDRESS in
                    ElementTree.tostring(response.Compile()))
    self.assertTrue(response._app_request == app_request)
    self.assertFalse(response._err_not_found)
    self.assertTrue(response._app_data is match)

    self._properties.install_app_index.Find.assert_called_once_with(app_request)
    self._properties.update_app_index.Find.assert_not_called()

  def testAppResponseNoMatch(self):
    """Tests AppResponse generation for update request with an unknown appid."""
    app_request = GenerateAppRequest()
    self._properties.update_app_index.Find.return_value = None
    self._properties.update_app_index.Contains.return_value = False

    response = nebraska.Response.AppResponse(app_request, self._properties)

    self.assertTrue(response._app_request == app_request)
    self.assertTrue(response._err_not_found)
    self.assertTrue(response._app_data is None)

    self._properties.update_app_index.Find.assert_called_once_with(app_request)
    self._properties.install_app_index.Find.assert_not_called()

  def testAppResponseNoUpdate(self):
    """Tests AppResponse generation for update request with no new versions."""
    # GIVEN an update request.
    app_request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.UPDATE)
    # GIVEN Nebraska does not find an update.
    self._properties.update_app_index.Find.return_value = None
    # GIVEN it is a valid app.
    self._properties.update_app_index.Contains.return_value = True

    # WHEN Nebraska sends a response.
    response = nebraska.Response.AppResponse(app_request, self._properties)

    # THEN the response contains <updatecheck status="noupdate"/>.
    update_check_tag = response.Compile().findall('updatecheck')[0]
    self.assertTrue(update_check_tag.attrib['status'] == 'noupdate')

  def testAppResponseNoUpdateFlag(self):
    """Tests status="noupdate" is included in the response."""
    app_request = GenerateAppRequest()
    match = GenerateAppData()
    self._properties.update_app_index.Find.return_value = match
    self._properties.update_app_index.Contains.return_value = True
    self._properties.no_update = True

    response = nebraska.Response.AppResponse(
        app_request, self._properties).Compile()
    update_check_tag = response.findall('updatecheck')[0]
    self.assertTrue(update_check_tag.attrib['status'] == 'noupdate')

  def testAppResponsePing(self):
    """Tests AppResponse generation for no-op with a ping request."""
    app_request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.EVENT, ping=True)
    self._properties.update_app_index.Find.return_value = None
    self._properties.update_app_index.Contains.return_value = True

    response = nebraska.Response.AppResponse(app_request, self._properties)

    self.assertTrue(response._app_request == app_request)
    self.assertFalse(response._err_not_found)
    self.assertTrue(response._app_data is None)

    self._properties.update_app_index.Find.assert_not_called()
    self._properties.install_app_index.Find.assert_not_called()

  def testAppResponseEvent(self):
    """Tests AppResponse generation for requests with events."""
    app_request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.EVENT)
    self._properties.update_app_index.Find.return_value = None
    self._properties.update_app_index.Contains.return_value = True

    response = nebraska.Response.AppResponse(app_request, self._properties)

    self.assertTrue(response._app_request == app_request)
    self.assertFalse(response._err_not_found)
    self.assertTrue(response._app_data is None)

    self._properties.update_app_index.Find.assert_not_called()
    self._properties.install_app_index.Find.assert_not_called()

  def testCompileSuccess(self):
    """Tests successful compilation of an AppData instance."""
    app_request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.INSTALL)
    match = GenerateAppData()
    self._properties.install_app_index.Find.return_value = match

    response = nebraska.Response.AppResponse(app_request, self._properties)
    compiled_response = response.Compile()

    update_check_tag = compiled_response.find('updatecheck')
    url_tag = compiled_response.find('updatecheck/urls/url')
    manifest_tag = compiled_response.find('updatecheck/manifest')
    package_tag = compiled_response.find(
        'updatecheck/manifest/packages/package')
    action_tag = compiled_response.findall(
        'updatecheck/manifest/actions/action')[1]

    self.assertTrue(url_tag is not None)
    self.assertTrue(manifest_tag is not None)
    self.assertTrue(package_tag is not None)
    self.assertTrue(action_tag is not None)
    self.assertTrue(action_tag.attrib['sha256'] == match.sha256)

    self.assertTrue(compiled_response.attrib['status'] == 'ok')
    self.assertTrue(update_check_tag.attrib['status'] == 'ok')

    self.assertTrue(compiled_response.attrib['appid'] == match.appid)
    self.assertTrue(url_tag.attrib['codebase'] == _INSTALL_PAYLOADS_ADDRESS)
    self.assertTrue(manifest_tag.attrib['version'] == match.target_version)
    self.assertTrue(package_tag.attrib['hash_sha256'] == match.sha256_hex)
    self.assertTrue(package_tag.attrib['fp'] == '1.%s' % match.sha256_hex)
    self.assertTrue(package_tag.attrib['name'] == match.name)
    self.assertTrue(package_tag.attrib['size'] == match.size)
    self.assertTrue(
        action_tag.attrib['ChromeOSVersion'] == match.target_version)
    self.assertTrue(action_tag.attrib['IsDeltaPayload'] == 'true' if
                    match.is_delta else 'false')
    self.assertFalse('deadline' in action_tag.attrib)
    self.assertFalse('PublicKeyRsa' in action_tag.attrib)

  def testCriticalUpdate(self):
    """Tests correct response for critical updates."""
    app_request = GenerateAppRequest()
    match = GenerateAppData()
    self._properties.update_app_index.Find.return_value = match
    self._properties.critical_update = True
    response = nebraska.Response.AppResponse(
        app_request, self._properties).Compile()
    action_tag = response.findall(
        'updatecheck/manifest/actions/action')[1]
    self.assertTrue(action_tag.attrib['deadline'] == 'now')

  def testPublicKey(self):
    """Tests public key is included in the response."""
    app_request = GenerateAppRequest()
    match = GenerateAppData(include_public_key=True)
    self._properties.update_app_index.Find.return_value = match
    response = nebraska.Response.AppResponse(
        app_request, self._properties).Compile()
    action_tag = response.findall(
        'updatecheck/manifest/actions/action')[1]
    self.assertTrue(action_tag.attrib['PublicKeyRsa'] == match.public_key)

if __name__ == '__main__':
  # Disable logging so it doesn't pollute the unit test output. Failures and
  # exceptions are still shown.
  logging.disable(logging.CRITICAL)

  unittest.main()
