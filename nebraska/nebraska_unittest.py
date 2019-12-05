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
_UPDATE_PAYLOADS_ADDRESS = 'www.google.com/update/'
_INSTALL_PAYLOADS_ADDRESS = 'www.google.com/install/'

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
      nebraska.AppIndex.AppData.METADATA_SIG_KEY:
          'Dr4RFXYgcfvFHV/0VRQs+SCQmz15Sk04LLEDswtvng8BqNbBXA7VvPUhpCgX5T/t7cwP'
          'xTUHJVtxIREuBZpyIQxJQFZATspaClelpKBwadQzj7dpfShLpcbdlfM8qbLjIbXfC2Vy'
          'mw03Mwf38lm0Fm75SANSTW9S4arPDf3sy9YGuqesnEJXyT3ZSGyK+Xto79zlURUXCgmi'
          'a6t7MaJE3ZbCdeF4EiEMPDsipqj9ggmKwiCdUl2+RxTznX/015XFiBhogLrx9RCPHTR8'
          'nLz0H9RcRhIvMd+8g4kHUZTDvjCvG5EZHpIKk8FK8z0zY/LWVr738evwuNNwyKIazkQB'
          'TA==',
      nebraska.AppIndex.AppData.METADATA_SIZE_KEY: '42',
      nebraska.AppIndex.AppData.SHA256_HEX_KEY:
      '886fd274745b4fa8d1f253cff11242fac07a29522b1bb9e028ab1480353d3160',
  }
  if include_public_key:
    data[nebraska.AppIndex.AppData.PUBLIC_KEY_RSA_KEY] = 'foo-public-key'
  return nebraska.AppIndex.AppData(data)


def GenerateAppRequest(request_type=nebraska.Request.RequestType.UPDATE,
                       appid='foo', version='1.0.0', delta_okay=False,
                       event=False, event_type='1', event_result='1',
                       update_check=True, ping=False, rollback_allowed=False):
  """Generates an app request test instance."""
  APP_TEMPLATE = """<app appid="" version="" delta_okay=""
track="foo-channel" board="foo-board"> </app>"""
  PING_TEMPLATE = """<ping active="1" a="1" r="1"></ping>"""
  UPDATE_CHECK_TEMPLATE = """<updatecheck></updatecheck>"""
  EVENT_TEMPLATE = """<event eventtype="3" eventresult="1"></event>"""

  app = ElementTree.fromstring(APP_TEMPLATE)
  app.set('appid', appid)
  app.set('version', version)
  app.set('delta_okay', str(bool(delta_okay)).lower())

  if ping:
    app.append(ElementTree.fromstring(PING_TEMPLATE))
  if update_check:
    update_check = ElementTree.fromstring(UPDATE_CHECK_TEMPLATE)
    app.append(update_check)
    if rollback_allowed:
      update_check.set('rollback_allowed', 'true')
  if event:
    event_tag = ElementTree.fromstring(EVENT_TEMPLATE)
    event_tag.set('eventtype', event_type)
    event_tag.set('eventresult', event_result)
    app.append(event_tag)

  return nebraska.Request.AppRequest(app, request_type)


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
    nebraska_props = nebraska.NebraskaProperties(
        update_payloads_address=_PAYLOAD_ADDRESS)
    nebraska_obj = nebraska.Nebraska(nebraska_props=nebraska_props)
    self.server.owner = nebraska.NebraskaServer(nebraska_obj)


class NebraskaTest(unittest.TestCase):
  """Test Nebraska."""

  def testDefaultInstallPayloadsAddress(self):
    """Tests the default install_payloads_address is correctly set."""
    update_addr = 'foo/update/'
    install_addr = 'foo/install/'
    # pylint: disable=protected-access
    nebraska_props = nebraska.NebraskaProperties(
        update_payloads_address=update_addr,
        install_payloads_address=install_addr)
    n = nebraska.Nebraska(nebraska_props=nebraska_props)
    self.assertEqual(n._nebraska_props.install_payloads_address, install_addr)
    self.assertEqual(n._nebraska_props.update_payloads_address, update_addr)

    nebraska_props = nebraska.NebraskaProperties(
        update_payloads_address=update_addr)
    n = nebraska.Nebraska(nebraska_props=nebraska_props)
    self.assertEqual(n._nebraska_props.install_payloads_address, update_addr)

    n = nebraska.Nebraska()
    self.assertEqual(n._nebraska_props.update_payloads_address, '')
    self.assertEqual(n._nebraska_props.install_payloads_address, '')


class NebraskaHandlerTest(unittest.TestCase):
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

  @mock.patch.object(nebraska.Nebraska, 'GetResponseToRequest',
                     return_value='foobar')
  @mock.patch.object(nebraska, 'Request')
  def testDoPostSuccess(self, _, response_mock):
    """Tests do_POST success."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/update'

    nebraska_handler.do_POST()

    response_mock.assert_called_once()
    nebraska_handler._SendResponse.assert_called_once_with(
        'application/xml', response_mock.return_value)

  @mock.patch.object(nebraska.Nebraska, 'GetResponseToRequest')
  @mock.patch.object(nebraska, 'Request')
  def testDoPostSuccessWithCriticalUpdate(self, _, response_mock):
    """Tests do_POST success with critical_update query string in URL."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/update/?critical_update=True'

    nebraska_handler.do_POST()

    response_mock.assert_called_once()
    self.assertTrue(
        response_mock.call_args_list[0].response_props.critical_update)

  @mock.patch.object(nebraska.Nebraska, 'GetResponseToRequest')
  @mock.patch.object(nebraska, 'Request')
  def testDoPostSuccessWithNoUpdate(self, _, response_mock):
    """Tests do_POST success with no_update query string in URL."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/update/?no_update=True'

    nebraska_handler.do_POST()

    response_mock.assert_called_once()
    self.assertTrue(response_mock.call_args_list[0].response_props.no_update)

  def testDoPostInvalidPath(self):
    """Test do_POST invalid path."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/invalid-path'
    nebraska_handler.do_POST()

    nebraska_handler.send_error.assert_called_once_with(
        http_client.BAD_REQUEST,
        'The requested path "invalid-path" was not found!')

  @mock.patch.object(nebraska, 'traceback')
  @mock.patch.object(nebraska.Request, 'ParseRequest',
                     side_effect=nebraska.InvalidRequestError)
  def testDoPostInvalidRequest(self, _, traceback_mock):
    """Test do_POST invalid request."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/update'
    nebraska_handler.do_POST()

    self.assertEqual(traceback_mock.format_exc.call_count, 2)
    nebraska_handler.send_error.assert_called_once_with(
        http_client.INTERNAL_SERVER_ERROR, traceback_mock.format_exc())

  @mock.patch.object(nebraska, 'traceback')
  @mock.patch.object(nebraska, 'Response')
  def testDoPostInvalidResponse(self, response_mock, traceback_mock):
    """Tests do_POST invalid response handling."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/update'

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
        'application/json', b'[]')

  def testDoGetFailureBadPath(self):
    """Tests do_GET failure on bad path."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/invalid-path'

    nebraska_handler.do_GET()
    nebraska_handler.send_error(http_client.BAD_REQUEST, mock.ANY)


class NebraskaServerTest(unittest.TestCase):
  """Test NebraskaServer."""

  def testStart(self):
    """Tests Start."""
    nebraska_props = nebraska.NebraskaProperties(_PAYLOAD_ADDRESS)
    nebraska_instance = nebraska.Nebraska(nebraska_props=nebraska_props)
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
    nebraska_props = nebraska.NebraskaProperties(_PAYLOAD_ADDRESS)
    nebraska_instance = nebraska.Nebraska(nebraska_props=nebraska_props)
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
    nebraska_props = nebraska.NebraskaProperties(_PAYLOAD_ADDRESS)
    nebraska_instance = nebraska.Nebraska(nebraska_props=nebraska_props)
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


class AppIndexTest(unittest.TestCase):
  """Test AppIndex."""

  def testScanEmpty(self):
    """Tests Scan on an empty directory."""
    with mock.patch('os.listdir') as listdir_mock:
      with mock.patch.object(builtins, 'open') as open_mock:
        listdir_mock.return_value = []
        app_index = nebraska.AppIndex(_INSTALL_DIR)
        self.assertFalse(app_index._index)
        listdir_mock.assert_called_once_with(_INSTALL_DIR)
        open_mock.assert_not_called()

  def testScanNoJson(self):
    """Tests Scan on a directory with no JSON files."""
    with mock.patch('os.listdir') as listdir_mock:
      with mock.patch.object(builtins, 'open') as open_mock:
        listdir_mock.return_value = ['foo.bin', 'bar.bin', 'json']
        app_index = nebraska.AppIndex(_INSTALL_DIR)
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
          nebraska.AppIndex(_INSTALL_DIR)

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
          nebraska.AppIndex(_INSTALL_DIR)

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

        request = GenerateAppRequest(appid='random')
        # It will match against the AppData with an empty appid.
        self.assertTrue(app_index.Contains(request))


class AppDataTest(unittest.TestCase):
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


class RequestTest(unittest.TestCase):
  """Tests for Request class."""

  def testParseRequestInvalidXML(self):
    """Tests ParseRequest handling of invalid XML."""
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request(XMLStrings.INVALID_XML_REQUEST)

  def testParseRequestInvalidApp(self):
    """Tests ParseRequest handling of invalid app requests."""
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request(XMLStrings.INVALID_APP_REQUEST)

  def testParseRequestInvalidInstall(self):
    """Tests ParseRequest handling of invalid app requests."""
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request(XMLStrings.INVALID_INSTALL_REQUEST)

  def testParseRequestInvalidNoop(self):
    """Tests ParseRequest handling of invalid mixed no-op request."""
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request(XMLStrings.INVALID_NOOP_REQUEST)

  def testParseRequestMissingAtLeastOneRequiredAttr(self):
    """Tests ParseRequest handling of missing required attributes in request."""
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request(XMLStrings.MISSING_REQUIRED_ATTR_REQUEST)

  def testParseRequestMismatchedVersion(self):
    """Tests ParseRequest handling of mismatched version numbers."""
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request(XMLStrings.MISMATCHED_VERSION_ATTR_REQUEST)

  def testParseRequestInstall(self):
    """Tests ParseRequest handling of install requests."""
    app_requests = nebraska.Request(XMLStrings.INSTALL_REQUEST).app_requests

    self.assertEqual(app_requests[0].request_type,
                     nebraska.Request.RequestType.INSTALL)
    self.assertEqual(app_requests[1].request_type,
                     nebraska.Request.RequestType.INSTALL)
    self.assertEqual(app_requests[2].request_type,
                     nebraska.Request.RequestType.INSTALL)

    self.assertEqual(app_requests[0].appid, 'platform')
    self.assertEqual(app_requests[1].appid, 'foo')
    self.assertEqual(app_requests[2].appid, 'bar')

    self.assertEqual(app_requests[0].version, '1.0.0')
    self.assertEqual(app_requests[1].version, '1.0.0')
    self.assertEqual(app_requests[2].version, '1.0.0')

  def testParseRequestUpdate(self):
    """Tests ParseRequest handling of update requests."""
    app_requests = nebraska.Request(XMLStrings.UPDATE_REQUEST).app_requests

    self.assertEqual(app_requests[0].request_type,
                     nebraska.Request.RequestType.UPDATE)
    self.assertEqual(app_requests[1].request_type,
                     nebraska.Request.RequestType.UPDATE)
    self.assertEqual(app_requests[2].request_type,
                     nebraska.Request.RequestType.UPDATE)

    self.assertEqual(app_requests[0].appid, 'platform')
    self.assertEqual(app_requests[1].appid, 'foo')
    self.assertEqual(app_requests[2].appid, 'bar')

    self.assertEqual(app_requests[0].version, '1.0.0')
    self.assertEqual(app_requests[1].version, '1.0.0')
    self.assertEqual(app_requests[2].version, '1.0.0')

    self.assertTrue(app_requests[0].delta_okay)
    self.assertTrue(app_requests[1].delta_okay)
    self.assertFalse(app_requests[2].delta_okay)

  def testParseRequestEventPing(self):
    """Tests ParseRequest handling of event ping requests."""
    app_requests = nebraska.Request(XMLStrings.EVENT_REQUEST).app_requests

    self.assertEqual(app_requests[0].request_type,
                     nebraska.Request.RequestType.EVENT)
    self.assertEqual(app_requests[0].appid, 'platform')
    self.assertEqual(app_requests[0].event_type, 3)
    self.assertEqual(app_requests[0].event_result, 1)
    self.assertEqual(app_requests[0].previous_version, '1')

  def testDetectingPlatformAppRequest(self):
    """Tests we correctly identify platform VS. DLC requests"""
    request = GenerateAppRequest(appid='foo-platform')
    self.assertTrue(request.is_platform)

    request = GenerateAppRequest(appid='')
    self.assertTrue(request.is_platform)

    request = GenerateAppRequest(appid='foo-platform_dlc')
    self.assertFalse(request.is_platform)

    request = GenerateAppRequest(appid='_dlc')
    self.assertFalse(request.is_platform)


class ResponseTest(unittest.TestCase):
  """Tests for Response class."""

  def testGetXMLStringSuccess(self):
    """Tests GetXMLString success."""
    nebraska_props = nebraska.NebraskaProperties(
        update_payloads_address=_UPDATE_PAYLOADS_ADDRESS,
        install_payloads_address=_INSTALL_PAYLOADS_ADDRESS)

    app_list = (
        GenerateAppData(is_delta=True, source_version='0.9.0'),
        GenerateAppData(appid='bar', is_delta=True, source_version='1.9.0'),
        GenerateAppData(appid='foobar'))
    nebraska_props.update_app_index._index = app_list

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

    response = nebraska.Response(request, nebraska_props,
                                 nebraska.ResponseProperties()).GetXMLString()
    response_root = ElementTree.fromstring(response)
    app_responses = response_root.findall('app')

    self.assertEqual(len(app_responses), 3)
    for response, app in zip(app_responses, app_list):
      self.assertEqual(response.attrib['appid'], app.appid)
      self.assertIsNotNone(response.find('ping'))


class AppResponseTest(unittest.TestCase):
  """Tests for AppResponse class."""

  def setUp(self):
    """Setting up common parameters."""
    self._nebraska_props = nebraska.NebraskaProperties(
        update_payloads_address=_UPDATE_PAYLOADS_ADDRESS,
        install_payloads_address=_INSTALL_PAYLOADS_ADDRESS)
    self._response_props = nebraska.ResponseProperties()

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=GenerateAppData())
  def testAppResponseUpdate(self, find_mock):
    """Tests AppResponse for an update request with matching payload."""
    app_request = GenerateAppRequest()
    match = find_mock.return_value
    # Setting the install app index object to None to make sure it is not being
    # called.
    self._nebraska_props.install_app_index.Find = None

    response = nebraska.Response.AppResponse(app_request,
                                             self._nebraska_props,
                                             self._response_props)

    self.assertIn(_UPDATE_PAYLOADS_ADDRESS.encode('utf-8'),
                  ElementTree.tostring(response.Compile()))
    self.assertEqual(response._app_request, app_request)
    self.assertFalse(response._err_not_found)
    self.assertIs(response._app_data, match)
    find_mock.assert_called_once_with(app_request)

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=GenerateAppData())
  def testAppResponseInstall(self, find_mock):
    """Tests AppResponse generation for install request with match."""
    app_request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.INSTALL)
    match = find_mock.return_value
    # Setting the update app index object to None to make sure it is not being
    # called.
    self._nebraska_props.update_app_index.Find = None

    response = nebraska.Response.AppResponse(app_request,
                                             self._nebraska_props,
                                             self._response_props)

    self.assertIn(_INSTALL_PAYLOADS_ADDRESS.encode('utf-8'),
                  ElementTree.tostring(response.Compile()))
    self.assertEqual(response._app_request, app_request)
    self.assertFalse(response._err_not_found)
    self.assertIs(response._app_data, match)
    find_mock.assert_called_once_with(app_request)

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=None)
  @mock.patch.object(nebraska.AppIndex, 'Contains', return_value=False)
  def testAppResponseNoMatch(self, contains_mock, find_mock):
    """Tests AppResponse generation for update request with an unknown appid."""
    app_request = GenerateAppRequest()
    response = nebraska.Response.AppResponse(app_request,
                                             self._nebraska_props,
                                             self._response_props)

    self.assertEqual(response._app_request, app_request)
    self.assertTrue(response._err_not_found)
    self.assertIsNone(response._app_data)
    find_mock.assert_called_once_with(app_request)
    contains_mock.assert_called_once_with(app_request)

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=None)
  @mock.patch.object(nebraska.AppIndex, 'Contains', return_value=True)
  # pylint: disable=unused-argument
  def testAppResponseNoUpdate(self, contains_mock, find_mock):
    """Tests AppResponse generation for update request with no new versions."""
    # GIVEN an update request.
    app_request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.UPDATE)

    # WHEN Nebraska sends a response.
    response = nebraska.Response.AppResponse(app_request,
                                             self._nebraska_props,
                                             self._response_props)

    # THEN the response contains <updatecheck status="noupdate"/>.
    update_check_tag = response.Compile().findall('updatecheck')[0]
    self.assertEqual(update_check_tag.attrib['status'], 'noupdate')

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=GenerateAppData())
  @mock.patch.object(nebraska.AppIndex, 'Contains', return_value=True)
  # pylint: disable=unused-argument
  def testAppResponseNoUpdateFlag(self, contains_mock, find_mock):
    """Tests status="noupdate" is included in the response."""
    app_request = GenerateAppRequest()
    self._response_props.no_update = True

    response = nebraska.Response.AppResponse(
        app_request, self._nebraska_props, self._response_props).Compile()

    update_check_tag = response.findall('updatecheck')[0]
    self.assertEqual(update_check_tag.attrib['status'], 'noupdate')

  @mock.patch.object(nebraska.AppIndex, 'Find')
  @mock.patch.object(nebraska.AppIndex, 'Contains', return_value=True)
  def testAppResponsePing(self, contains_mock, find_mock):
    """Tests AppResponse generation for no-op with a ping request."""
    app_request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.EVENT, ping=True)
    response = nebraska.Response.AppResponse(app_request,
                                             self._nebraska_props,
                                             self._response_props)

    self.assertEqual(response._app_request, app_request)
    self.assertFalse(response._err_not_found)
    self.assertIsNone(response._app_data)
    find_mock.assert_not_called()
    contains_mock.assert_not_called()

  @mock.patch.object(nebraska.AppIndex, 'Find')
  @mock.patch.object(nebraska.AppIndex, 'Contains')
  def testAppResponseEvent(self, contains_mock, find_mock):
    """Tests AppResponse generation for requests with events."""
    app_request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.EVENT)

    response = nebraska.Response.AppResponse(app_request,
                                             self._nebraska_props,
                                             self._response_props)

    self.assertEqual(response._app_request, app_request)
    self.assertFalse(response._err_not_found)
    self.assertIsNone(response._app_data)
    find_mock.assert_not_called()
    contains_mock.assert_not_called()

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=GenerateAppData())
  def testCompileSuccess(self, find_mock):
    """Tests successful compilation of an AppData instance."""
    app_request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.INSTALL)
    match = find_mock.return_value

    response = nebraska.Response.AppResponse(app_request,
                                             self._nebraska_props,
                                             self._response_props)
    compiled_response = response.Compile()

    update_check_tag = compiled_response.find('updatecheck')
    url_tags = compiled_response.findall('updatecheck/urls/url')
    manifest_tag = compiled_response.find('updatecheck/manifest')
    package_tag = compiled_response.find(
        'updatecheck/manifest/packages/package')
    action_tag = compiled_response.findall(
        'updatecheck/manifest/actions/action')[1]

    self.assertEqual(len(url_tags), 1)
    self.assertEqual(url_tags[0].attrib['codebase'], _INSTALL_PAYLOADS_ADDRESS)
    self.assertIsNotNone(manifest_tag)
    self.assertIsNotNone(package_tag)
    self.assertIsNotNone(action_tag)
    self.assertEqual(action_tag.attrib['sha256'], match.sha256)
    self.assertEqual(action_tag.attrib['DisablePayloadBackoff'], 'false')
    self.assertEqual(compiled_response.attrib['status'], 'ok')
    self.assertEqual(compiled_response.attrib['appid'], match.appid)
    self.assertEqual(update_check_tag.attrib['status'], 'ok')
    self.assertEqual(manifest_tag.attrib['version'], match.target_version)
    self.assertEqual(package_tag.attrib['hash_sha256'].encode('utf-8'),
                     match.sha256_hex)
    self.assertEqual(package_tag.attrib['fp'], '1.%s' % match.sha256_hex)
    self.assertEqual(package_tag.attrib['name'], match.name)
    self.assertEqual(package_tag.attrib['size'], match.size)
    self.assertEqual(
        action_tag.attrib['ChromeOSVersion'], match.target_version)
    self.assertEqual(action_tag.attrib['IsDeltaPayload'],
                     str(match.is_delta).lower())
    self.assertNotIn('deadline', action_tag.attrib)
    self.assertNotIn('PublicKeyRsa', action_tag.attrib)
    self.assertNotIn('MaxFailureCountPerUrl', action_tag)
    self.assertNotIn('_is_rollback', update_check_tag.attrib)

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=GenerateAppData())
  # pylint: disable=unused-argument
  def testCriticalUpdate(self, find_mock):
    """Tests correct response for critical updates."""
    app_request = GenerateAppRequest()
    self._response_props.critical_update = True

    response = nebraska.Response.AppResponse(
        app_request, self._nebraska_props, self._response_props).Compile()

    action_tag = response.findall(
        'updatecheck/manifest/actions/action')[1]
    self.assertEqual(action_tag.attrib['deadline'], 'now')

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=GenerateAppData())
  # pylint: disable=unused-argument
  def testCriticalInstall(self, find_mock):
    """Tests correct response for critical installs."""
    app_request = GenerateAppRequest(
        request_type=nebraska.Request.RequestType.INSTALL)
    self._response_props.critical_update = True

    response = nebraska.Response.AppResponse(
        app_request, self._nebraska_props, self._response_props).Compile()

    action_tag = response.findall(
        'updatecheck/manifest/actions/action')[1]
    self.assertEqual(action_tag.attrib['deadline'], 'now')

  @mock.patch.object(nebraska.AppIndex, 'Find',
                     return_value=GenerateAppData(include_public_key=True))
  def testPublicKey(self, find_mock):
    """Tests public key is included in the response."""
    app_request = GenerateAppRequest()

    response = nebraska.Response.AppResponse(
        app_request, self._nebraska_props, self._response_props).Compile()

    action_tag = response.findall(
        'updatecheck/manifest/actions/action')[1]
    self.assertEqual(action_tag.attrib['PublicKeyRsa'],
                     find_mock.return_value.public_key)

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=GenerateAppData())
  def testRollback(self, _):
    """Tests rollback parametes are setup correctly."""
    app_request = GenerateAppRequest(rollback_allowed=True)
    self._response_props.is_rollback = True

    response = nebraska.Response.AppResponse(
        app_request, self._nebraska_props, self._response_props).Compile()

    update_check_tag = response.find('updatecheck')
    index_strs = ['', '_0', '_1', '_2', '_3', '_4']
    self.assertEqual(update_check_tag.attrib['_is_rollback'], 'true')
    for idx in index_strs:
      self.assertEqual(update_check_tag.attrib['_firmware_version' + idx],
                       nebraska._FIRMWARE_VER)
      self.assertEqual(update_check_tag.attrib['_kernel_version' + idx],
                       nebraska._KERNEL_VER)

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=GenerateAppData())
  def testNotRollback(self, _):
    """Tests that we should not do rollback if it was not requested."""
    app_request = GenerateAppRequest(rollback_allowed=False)
    self._response_props.is_rollback = True

    response = nebraska.Response.AppResponse(
        app_request, self._nebraska_props, self._response_props).Compile()

    update_check_tag = response.find('updatecheck')
    self.assertNotIn('_is_rollback', update_check_tag.attrib)

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=GenerateAppData())
  def testFailuresPerUrl(self, _):
    """Tests response for number of failures allowed per URL."""
    app_request = GenerateAppRequest()

    self._response_props.failures_per_url = 1
    response = nebraska.Response.AppResponse(
        app_request, self._nebraska_props, self._response_props).Compile()

    action_tag = response.findall(
        'updatecheck/manifest/actions/action')[1]
    self.assertEqual(action_tag.attrib['MaxFailureCountPerUrl'], 1)

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=GenerateAppData())
  def testDisablePayloadBackoff(self, _):
    """Tests disabling payload backoff on the client."""
    app_request = GenerateAppRequest()
    self._response_props.disable_payload_backoff = True

    response = nebraska.Response.AppResponse(
        app_request, self._nebraska_props, self._response_props).Compile()

    action_tag = response.findall(
        'updatecheck/manifest/actions/action')[1]
    self.assertEqual(action_tag.attrib['DisablePayloadBackoff'], 'true')

  @mock.patch.object(nebraska.AppIndex, 'Find', return_value=GenerateAppData())
  def testNumUrls(self, _):
    """Tests the number of URLs are passed correctly."""
    app_request = GenerateAppRequest()
    self._response_props.num_urls = 2

    response = nebraska.Response.AppResponse(
        app_request, self._nebraska_props, self._response_props).Compile()

    url_tags = response.findall('updatecheck/urls/url')
    self.assertEqual(len(url_tags), 2)

if __name__ == '__main__':
  # Disable logging so it doesn't pollute the unit test output. Failures and
  # exceptions are still shown.
  logging.disable(logging.CRITICAL)

  unittest.main()
