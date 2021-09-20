#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittests for Nebraska server."""

from __future__ import print_function

import base64
import builtins
import collections
import http
import json
import logging
import os
import shutil
import tempfile
import unittest

from xml.etree import ElementTree
import mock

import nebraska


_NEBRASKA_PORT = 11235
_PAYLOADS_ADDRESS = 'www.google.com/update/'

# pylint: disable=protected-access

def _ExcludeNoneValuesFromDict(dictionary):
  """Returns the input dictionary but keys with None values removed.

  Args:
    dictionary: input dict object.

  Returns:
    a dict object containing all the items of intput dictionary except the ones
    which have None value.
  """
  return {k: v for k, v in dictionary.items() if v is not None}


class NebraskaBaseTest(unittest.TestCase):
  """Base class for all nebraska unittests."""

  def setUp(self):
    """Sets up the base test fixture."""
    self.tempdir = tempfile.mkdtemp()

  def tearDown(self):
    """Cleans up the text fixture."""
    shutil.rmtree(self.tempdir)

  def GenerateAppData(self, path='foo.json', appid='foo', name='foo',
                      is_delta=False, target_version='2.0.0',
                      source_version=None, include_public_key=False):
    """Generates a TestAppData test instance.

    Returns:
      The resulting data in a dictionary format.
    """
    TestAppData = collections.namedtuple('TestAppData', [
        nebraska.AppIndex.AppData.APPID_KEY,
        nebraska.AppIndex.AppData.NAME_KEY,
        nebraska.AppIndex.AppData.TARGET_VERSION_KEY,
        nebraska.AppIndex.AppData.IS_DELTA_KEY,
        nebraska.AppIndex.AppData.SOURCE_VERSION_KEY,
        nebraska.AppIndex.AppData.SIZE_KEY,
        nebraska.AppIndex.AppData.METADATA_SIG_KEY,
        nebraska.AppIndex.AppData.METADATA_SIZE_KEY,
        nebraska.AppIndex.AppData.SHA256_HEX_KEY,
        nebraska.AppIndex.AppData.PUBLIC_KEY_RSA_KEY,
    ])

    data = TestAppData(
        appid,
        name,
        target_version,
        is_delta,
        source_version,
        '9001',
        'Dr4RFXYgcfvFHV/0VRQs+SCQmz15Sk04LLEDswtvng8BqNbBXA7VvPUhpCgX5T/t7cwP'
        'xTUHJVtxIREuBZpyIQxJQFZATspaClelpKBwadQzj7dpfShLpcbdlfM8qbLjIbXfC2Vy'
        'mw03Mwf38lm0Fm75SANSTW9S4arPDf3sy9YGuqesnEJXyT3ZSGyK+Xto79zlURUXCgmi'
        'a6t7MaJE3ZbCdeF4EiEMPDsipqj9ggmKwiCdUl2+RxTznX/015XFiBhogLrx9RCPHTR8'
        'nLz0H9RcRhIvMd+8g4kHUZTDvjCvG5EZHpIKk8FK8z0zY/LWVr738evwuNNwyKIazkQB'
        'TA==',
        '42',
        '8gBImdKWgwAkwVNCij4u1QNJqkvzOUjoGWUw8ATvjgs=',
        # '886fd274745b4fa8d1f253cff11242fac07a29522b1bb9e028ab1480353d3160',
        'foo-public-key' if include_public_key else None,
    )

    with open(os.path.join(self.tempdir, path), 'w') as fp:
      dict_version = _ExcludeNoneValuesFromDict(data._asdict())
      json.dump(dict_version, fp)
    return data

def GenerateXMLAppRequest(appid='foo', version='1.0.0', delta_okay=False,
                          track='foo-channel', board='foo-board',
                          event=False, event_type='1', event_result='1',
                          previous_version=None, update_check=True, ping=False,
                          rollback_allowed=False):
  """Returns an XML app request."""
  app = ElementTree.Element('app', attrib=_ExcludeNoneValuesFromDict({
      'appid': appid,
      'version': version,
      'delta_okay': str(delta_okay).lower(),
      'track': track,
      'board': board,
  }))

  if ping:
    ping = ElementTree.Element('ping', attrib={'active': '1',
                                               'a': '1',
                                               'r': '1'})
    app.append(ping)
  if update_check:
    update_check = ElementTree.Element('updatecheck')
    if rollback_allowed:
      update_check.set('rollback_allowed', 'true')
    app.append(update_check)

  if event:
    event = ElementTree.Element('event', attrib=_ExcludeNoneValuesFromDict({
        'eventtype': event_type,
        'eventresult': event_result,
        'previousversion': previous_version,
    }))
    app.append(event)

  return app


def GenerateXMLRequest(apps):
  """Generates an XML request.

  Args:
    apps: A list of XML app requests.

  Returns:
    The generated XML request.
  """
  root = ElementTree.Element('request',
                             attrib={'requestid': 'foo-request-id',
                                     'sessionid': 'foo-session-id',
                                     'protocol': '3.0',
                                     'updater': 'ChromeOSUpdateEngine',
                                     'updaterversion': '0.1.0.0',
                                     'installsource': 'ondemandupdate',
                                     'ismachine': '1'})
  os_tag = ElementTree.Element('os', attrib={'version': 'Indy',
                                             'platform': 'Chrome OS',
                                             'sp': '12933.0.0_x86_64'})
  root.append(os_tag)
  for app in apps:
    root.append(app)

  return ElementTree.tostring(root, encoding='UTF-8', method='xml')


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
    nebraska_obj = nebraska.Nebraska()
    nebraska_obj.UpdateConfig(update_payloads_address=_PAYLOADS_ADDRESS)
    self.server.owner = nebraska.NebraskaServer(nebraska_obj)

class NebraskaHandlerTest(unittest.TestCase):
  """Test NebraskaHandler."""

  # TODO(ahasssni): Change these tests to be like tests in NebraskaTest.
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
        nebraska_handler.server.owner.nebraska._config.critical_update)

  @mock.patch.object(nebraska.Nebraska, 'GetResponseToRequest')
  @mock.patch.object(nebraska, 'Request')
  def testDoPostSuccessWithNoUpdate(self, _, response_mock):
    """Tests do_POST success with no_update query string in URL."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/update/?no_update=True'

    nebraska_handler.do_POST()

    response_mock.assert_called_once()
    self.assertTrue(nebraska_handler.server.owner.nebraska._config.no_update)

  def testDoPostInvalidPath(self):
    """Test do_POST invalid path."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/invalid-path'
    nebraska_handler.do_POST()

    nebraska_handler.send_error.assert_called_once_with(
        http.client.BAD_REQUEST,
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
        http.client.INTERNAL_SERVER_ERROR, traceback_mock.format_exc())

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
        http.client.INTERNAL_SERVER_ERROR, traceback_mock.format_exc())

  def testDoPostUpdateConfig(self):
    """Tests do_POST success for update_config API."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/update_config'
    nebraska_handler.rfile.read = lambda x: json.dumps(
        {'critical_update': True})

    self.assertFalse(
        nebraska_handler.server.owner.nebraska._config.critical_update)

    nebraska_handler.do_POST()

    self.assertTrue(
        nebraska_handler.server.owner.nebraska._config.critical_update)
    nebraska_handler._SendResponse.assert_called_once_with(
        'text/plain', b'Config set!')

  def testDoGetFailureBadPath(self):
    """Tests do_GET failure on bad path."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/invalid-path'

    nebraska_handler.do_GET()
    nebraska_handler.send_error(http.client.BAD_REQUEST, mock.ANY)

  def testDoGetHealthCheck(self):
    """Tests do_GET with health_check path."""
    nebraska_handler = MockNebraskaHandler()
    nebraska_handler.path = 'http://test.com/health_check'

    nebraska_handler.do_GET()
    nebraska_handler._SendResponse.assert_called_once_with(
        'text/plain', b'Nebraska is alive!')

class NebraskaServerTest(NebraskaBaseTest):
  """Test NebraskaServer."""

  def testStart(self):
    """Tests start of server."""
    nebraska_instance = nebraska.Nebraska()
    nebraska_instance.UpdateConfig(update_payloads_address=_PAYLOADS_ADDRESS)
    server = nebraska.NebraskaServer(nebraska_instance, port=_NEBRASKA_PORT)

    with mock.patch.object(http.server, 'HTTPServer') as server_mock:
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
    nebraska_instance = nebraska.Nebraska()
    nebraska_instance.UpdateConfig(update_payloads_address=_PAYLOADS_ADDRESS)
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
    nebraska_instance = nebraska.Nebraska()
    nebraska_instance.UpdateConfig(update_payloads_address=_PAYLOADS_ADDRESS)
    server = nebraska.NebraskaServer(nebraska_instance, port=_NEBRASKA_PORT,
                                     runtime_root=runtime_root)

    port_file = os.path.join(runtime_root, 'port')
    pid_file = os.path.join(runtime_root, 'pid')

    with mock.patch.object(http.server, 'HTTPServer'):
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

class NebraskaTest(NebraskaBaseTest):
  """Test AppIndex."""

  def testDefaultInstallPayloadsAddress(self):
    """Tests the default install_payloads_address is correctly set."""
    update_addr = 'foo/update/'
    install_addr = 'foo/install/'
    n = nebraska.Nebraska()
    n.UpdateConfig(update_payloads_address=update_addr,
                   install_payloads_address=install_addr)
    # pylint: disable=protected-access
    self.assertEqual(n._config.install_payloads_address, install_addr)
    self.assertEqual(n._config.update_payloads_address, update_addr)

  def testQueryDictToDict(self):
    """Tests QueryDictToDict() function"""
    self.assertEqual(nebraska.QueryDictToDict({
        'critical_update': 'True',
        'disable_payload_backoff': 'False',
        'eol_date': '10',
        'failures_per_url': '1',
        'no_update': 'True',
        'num_urls': ['0', '1'],
        'foo': 'bar',
    }), {
        'critical_update': True,
        'disable_payload_backoff': False,
        'eol_date': 10,
        'failures_per_url': 1,
        'no_update': True,
        'num_urls': 0,
    })

  def testDefaultRequestResponseXML(self):
    """Tests the default response to a request for an update check."""
    app_data = self.GenerateAppData()
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([GenerateXMLAppRequest()])
    response = neb.GetResponseToRequest(nebraska.Request(request))

    root = ElementTree.fromstring(response)
    apps = root.findall('app')
    self.assertEqual(len(apps), 1)
    self.assertEqual(apps[0].attrib['appid'], app_data.appid)
    self.assertEqual(apps[0].attrib['status'], 'ok')

    update_check = apps[0].find('updatecheck')
    self.assertEqual(update_check.attrib['status'], 'ok')
    self.assertNotIn('_is_rollback', update_check.attrib)
    self.assertNotIn('_firmware_version', update_check.attrib)
    self.assertNotIn('_kernel_version', update_check.attrib)
    self.assertNotIn('_eol_date', update_check.attrib)

    urls = update_check.findall('urls/url')
    self.assertEqual(len(urls), 1)
    self.assertEqual(urls[0].attrib['codebase'], _PAYLOADS_ADDRESS)

    manifest = update_check.find('manifest')
    self.assertIsNotNone(manifest)
    self.assertEqual(manifest.attrib['version'], app_data.target_version)

    actions = manifest.findall('actions/action')
    self.assertEqual(len(actions), 2)
    self.assertEqual(actions[1].attrib['sha256'], app_data.sha256_hex)
    self.assertEqual(actions[1].attrib['ChromeOSVersion'],
                     app_data.target_version)
    self.assertEqual(actions[1].attrib['DisablePayloadBackoff'], 'false')
    self.assertEqual(actions[1].attrib['MetadataSignatureRsa'],
                     app_data.metadata_signature)
    self.assertEqual(actions[1].attrib['MetadataSize'],
                     app_data.metadata_size)
    self.assertNotIn('MaxFailureCountPerUrl', actions[1].attrib)
    self.assertEqual(
        actions[1].attrib['ChromeOSVersion'], app_data.target_version)
    self.assertEqual(actions[1].attrib['IsDeltaPayload'],
                     str(app_data.is_delta).lower())
    self.assertNotIn('deadline', actions[1].attrib)
    self.assertNotIn('PublicKeyRsa', actions[1].attrib)
    self.assertNotIn('MaxFailureCountPerUrl', actions[1].attrib)

    package = manifest.find('packages/package')
    self.assertIsNotNone(package)
    self.assertEqual(package.attrib['name'], app_data.name)
    self.assertEqual(package.attrib['size'], app_data.size)
    sha256_hex = base64.b16encode(
        base64.b64decode(app_data.sha256_hex)).decode('utf-8')
    self.assertEqual(package.attrib['hash_sha256'], sha256_hex)
    self.assertEqual(package.attrib['fp'], '1.%s' % sha256_hex)

  def testScanEmpty(self):
    """Tests Scan on an empty directory."""
    with mock.patch('os.listdir') as listdir_mock:
      with mock.patch.object(builtins, 'open') as open_mock:
        listdir_mock.return_value = []
        app_index = nebraska.AppIndex('foo-dir')
        self.assertFalse(app_index._index)
        listdir_mock.assert_called_once_with('foo-dir')
        open_mock.assert_not_called()

  def testScanNoJson(self):
    """Tests Scan on a directory with no JSON files."""
    with mock.patch('os.listdir') as listdir_mock:
      with mock.patch.object(builtins, 'open') as open_mock:
        listdir_mock.return_value = ['foo.bin', 'bar.bin', 'json']
        app_index = nebraska.AppIndex('foo-dir')
        self.assertFalse(app_index._index)
        listdir_mock.assert_called_once_with('foo-dir')
        open_mock.assert_not_called()

  def testScanMultiple(self):
    """Tests Scan on a directory with multiple appids."""
    # Providing some mock properties and non-properties files.
    self.GenerateAppData('foo_update.json')
    self.GenerateAppData('foo_install.json', is_delta=True,
                         source_version='foo-version')
    self.GenerateAppData('bar_install.json', appid='bar')
    self.GenerateAppData('bar_update.json', appid='bar', is_delta=True,
                         source_version='foo-version')
    self.GenerateAppData('foo.blah', appid='foobar')

    # Make sure the Scan() scans all the files and at least correct App IDs
    # are generated. 'foo' and 'bar' App IDs should appear twice each.
    app_index = nebraska.AppIndex(self.tempdir)
    expected_appids = [x.appid for x in app_index._index]
    self.assertEqual(len(expected_appids), 4)
    self.assertEqual(expected_appids.count('foo'), 2)
    self.assertEqual(expected_appids.count('bar'), 2)

  def testScanInvalidJson(self):
    """Tests Scan with invalid JSON files."""
    self.GenerateAppData('foo_update.json')
    with mock.patch.object(builtins, 'open', side_effect=IOError):
      # Make sure we raise error when loading files raises one.
      with self.assertRaises(IOError):
        nebraska.AppIndex(self.tempdir)

  def testScanInvalidApp(self):
    """Tests Scan on JSON files lacking required keys."""
    self.GenerateAppData('foo_update.json', appid=None)
    # Make sure we raise error when properties files are invalid.
    with self.assertRaises(KeyError):
      nebraska.AppIndex(self.tempdir)

  def testMatch(self):
    """Tests different scenarios for correctly matching AppData."""
    # Providing some properties files.
    self.GenerateAppData('foo_install.json')
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)

    # Nothing found.
    request = GenerateXMLRequest([GenerateXMLAppRequest(appid='random')])
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    app = root.find('app')
    self.assertEqual(app.attrib['appid'], 'random')
    update_check = app.find('updatecheck')
    self.assertEqual(update_check.attrib['status'], 'noupdate')

    # Partially matches against the AppData with appid 'foo'.
    request = GenerateXMLRequest([GenerateXMLAppRequest(appid='mefoolme')])
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    app = root.find('app')
    self.assertEqual(app.attrib['appid'], 'mefoolme')
    update_check = app.find('updatecheck')
    self.assertEqual(update_check.attrib['status'], 'ok')

  def testMatchEmpty(self):
    """Tests Constains() correctly finds matching AppData with empty appid."""
    self.GenerateAppData('foo_update.json', appid='')
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([GenerateXMLAppRequest()])
    response = neb.GetResponseToRequest(nebraska.Request(request))

    root = ElementTree.fromstring(response)
    app = root.find('app')
    self.assertEqual(app.attrib['appid'], 'foo')
    update_check = app.find('updatecheck')
    self.assertEqual(update_check.attrib['status'], 'ok')

  def testMatchInstall(self):
    """Tests matching install requests."""
    self.GenerateAppData('foo.json')
    self.GenerateAppData('bar.json', appid='bar')
    neb = nebraska.Nebraska()
    neb.UpdateConfig(install_app_index=nebraska.AppIndex(self.tempdir),
                     install_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([
        # Not having an updatecheck tag in the platform App causes this to be an
        # install request.
        GenerateXMLAppRequest(appid='foo', update_check=False),
        GenerateXMLAppRequest(appid='bar', version='0.0.0.0')
    ])
    response = neb.GetResponseToRequest(nebraska.Request(request))

    apps = ElementTree.fromstring(response).findall('app')
    self.assertEqual(apps[0].attrib['status'], 'noupdate')
    update_check = apps[1].find('updatecheck')
    self.assertEqual(update_check.attrib['status'], 'ok')

  def testMatchDeltaAndFull(self):
    """Tests matching delta update request."""
    # Two properties file with the same App ID but one delta, one full.
    self.GenerateAppData('foo.json')
    self.GenerateAppData('bar.json', is_delta=True, source_version='1.0.0')
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)

    # Full payload.
    request = GenerateXMLRequest([GenerateXMLAppRequest(delta_okay=False)])
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    action = root.findall('app/updatecheck/manifest/actions/action')[1]
    self.assertEqual(action.attrib['IsDeltaPayload'], 'false')

    # Delta payload.
    request = GenerateXMLRequest([GenerateXMLAppRequest(delta_okay=True)])
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    action = root.findall('app/updatecheck/manifest/actions/action')[1]
    self.assertEqual(action.attrib['IsDeltaPayload'], 'true')

    # Forced full payload should return full payload.
    neb.UpdateConfig(full_payload=True)
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    action = root.findall('app/updatecheck/manifest/actions/action')[1]
    self.assertEqual(action.attrib['IsDeltaPayload'], 'false')

    # Delta payload should return delta payload.
    neb.UpdateConfig(full_payload=False)
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    action = root.findall('app/updatecheck/manifest/actions/action')[1]
    self.assertEqual(action.attrib['IsDeltaPayload'], 'true')

    # Forced delta payload when client can't get delta should be noupdate.
    request = GenerateXMLRequest([GenerateXMLAppRequest(delta_okay=False)])
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    update_check = root.find('app/updatecheck')
    self.assertEqual(update_check.attrib['status'], 'noupdate')

  def testMismatchAppDataAppID(self):
    """Tests appid mismatch."""
    self.GenerateAppData(appid='bar')
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([GenerateXMLAppRequest(appid='foo')])
    response = neb.GetResponseToRequest(nebraska.Request(request))

    update_check = ElementTree.fromstring(response).find('app/updatecheck')
    self.assertEqual(update_check.attrib['status'], 'noupdate')

  def testIgnoreAppDataAppID(self):
    """Tests ignoring appid."""
    self.GenerateAppData(appid='bar')
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS,
                     ignore_appid=True)
    request = GenerateXMLRequest([GenerateXMLAppRequest(appid='foo')])
    response = neb.GetResponseToRequest(nebraska.Request(request))

    update_check = ElementTree.fromstring(response).find('app/updatecheck')
    self.assertEqual(update_check.attrib['status'], 'ok')

  def testMatchCanaryAppId(self):
    """Tests matching update request with canary appid."""
    self.GenerateAppData(appid='1' * len(nebraska._CANARY_APP_ID) + 'foo')
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([
        GenerateXMLAppRequest(appid=nebraska._CANARY_APP_ID + 'foo')])
    response = neb.GetResponseToRequest(nebraska.Request(request))

    update_check = ElementTree.fromstring(response).find('app/updatecheck')
    self.assertEqual(update_check.attrib['status'], 'ok')

  def testAlreadyMatched(self):
    """Tests not matching an already matched app."""
    self.GenerateAppData()
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)

    # Two identical requests.
    request = GenerateXMLRequest([
        GenerateXMLAppRequest(),
        GenerateXMLAppRequest()
    ])
    response = neb.GetResponseToRequest(nebraska.Request(request))
    update_checks = ElementTree.fromstring(response).findall('app/updatecheck')
    self.assertEqual(update_checks[0].attrib['status'], 'ok')
    self.assertEqual(update_checks[1].attrib['status'], 'noupdate')

  def testInvalidXMLRequest(self):
    """Tests ParseRequest() handling of invalid XML."""
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request('invalid xml!')

  def testInvalidAppRequest(self):
    """Tests ParseRequest handling of invalid app requests."""
    request = GenerateXMLRequest([GenerateXMLAppRequest(appid=None)])
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request(request)

  def testParseRequestInvalidInstall(self):
    """Tests handling of invalid install app request (missing version)."""
    request = GenerateXMLRequest([
        GenerateXMLAppRequest(appid='foo', update_check=None),
        GenerateXMLAppRequest(appid='test', version=None),
    ])
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request(request)

  def testParseRequestInvalidNoop(self):
    """Tests ParseRequest handling of invalid mixed no-op request."""
    request = GenerateXMLRequest([
        GenerateXMLAppRequest(update_check=None),
        GenerateXMLAppRequest(appid='bar'),
        GenerateXMLAppRequest(appid='test', update_check=None),
    ])
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request(request)

  def testParseRequestMissingAtLeastOneRequiredAttr(self):
    """Tests ParseRequest handling of missing required attributes in request."""
    request = GenerateXMLRequest([
        GenerateXMLAppRequest(track=None),
        GenerateXMLAppRequest(appid='bar', track=None),
    ])
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request(request)

  def testParseRequestMismatchedVersionUpdate(self):
    """Tests ParseRequest handling of mismatched update version numbers."""
    request = GenerateXMLRequest([
        GenerateXMLAppRequest(version='1.0.0'),
        GenerateXMLAppRequest(appid='bar', version='2.0.0'),
    ])
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request(request)

  def testParseRequestMismatchedVersionInstall(self):
    """Tests ParseRequest handling of mismatched install version numbers."""
    request = GenerateXMLRequest([
        GenerateXMLAppRequest(version='1.0.0', update_check=None),
        GenerateXMLAppRequest(appid='bar', version='2.0.0'),
    ])
    with self.assertRaises(nebraska.InvalidRequestError):
      nebraska.Request(request)

  def testUpdateMultipleApps(self):
    """Tests update with multiple apps."""
    app_datas = [
        self.GenerateAppData('foo.json', appid='foo'),
        self.GenerateAppData('bar.json', appid='bar'),
        self.GenerateAppData('test.json', appid='test'),
    ]
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([
        GenerateXMLAppRequest(appid='foo'),
        GenerateXMLAppRequest(appid='bar'),
        GenerateXMLAppRequest(appid='test'),
    ])

    request = nebraska.Request(request)
    self.assertEqual(request.version, '1.0.0')

    response = neb.GetResponseToRequest(request)
    root = ElementTree.fromstring(response)
    apps = root.findall('app')
    self.assertEqual(len(app_datas), len(apps))
    for i, app in enumerate(apps):
      self.assertEqual(app.attrib['appid'], app_datas[i].appid)

    update_checks = root.findall('app/updatecheck')
    for i, update_check in enumerate(update_checks):
      self.assertEqual(update_check.attrib['status'], 'ok')
      manifest = update_check.find('manifest')
      self.assertEqual(manifest.attrib['version'],
                       app_datas[i].target_version)

  def testInstallMultipleApps(self):
    """Tests install for multiple apps."""
    app_datas = [
        self.GenerateAppData('foo.json', appid='foo'),
        self.GenerateAppData('bar.json', appid='bar'),
        self.GenerateAppData('test.json', appid='test'),
    ]
    neb = nebraska.Nebraska()
    neb.UpdateConfig(install_app_index=nebraska.AppIndex(self.tempdir),
                     install_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([
        GenerateXMLAppRequest(appid='foo', version='1.0.0', update_check=None),
        GenerateXMLAppRequest(appid='bar', version='0.0.0.0'),
        GenerateXMLAppRequest(appid='test', version='0.0.0.0'),
    ])

    request = nebraska.Request(request)
    self.assertEqual(request.version, '1.0.0')

    response = neb.GetResponseToRequest(request)
    root = ElementTree.fromstring(response)
    apps = root.findall('app')
    self.assertEqual(len(app_datas), len(apps))
    for i, app in enumerate(apps):
      self.assertEqual(app.attrib['appid'], app_datas[i].appid)

    update_checks = root.findall('app/updatecheck')
    self.assertEqual(update_checks[0].attrib['status'], 'ok')
    # Only the last two apps have updatechecks.
    for i in range(len(apps) - 1):
      manifest = update_checks[i].find('manifest')
      self.assertEqual(manifest.attrib['version'],
                       app_datas[i + 1].target_version)

  def testReturnNoUpdateStarting(self):
    """Tests return_noupdate_starting  with multiple apps."""
    self.GenerateAppData('foo.json', appid='foo')
    self.GenerateAppData('bar.json', appid='bar')
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([
        GenerateXMLAppRequest(appid='foo'),
        GenerateXMLAppRequest(appid='bar'),
    ])

    def TestHasUpdate(has_update_check):
      response = neb.GetResponseToRequest(nebraska.Request(request))
      root = ElementTree.fromstring(response)
      update_checks = root.findall('app/updatecheck')
      for update_check in update_checks:
        self.assertEqual(update_check.attrib['status'],
                         'ok' if has_update_check else 'noupdate')

    # With default value (0), it should always return an update.
    TestHasUpdate(True)
    TestHasUpdate(True)
    TestHasUpdate(True)

    # With value 1, it should start returning noupdate from the beginning.
    neb.UpdateConfig(return_noupdate_starting=1)
    TestHasUpdate(False)

    # With value N greater than 1, it should return update for first N-1.
    neb.UpdateConfig(return_noupdate_starting=3, no_update=False)
    TestHasUpdate(True)
    TestHasUpdate(True)
    TestHasUpdate(False)

  def testInvalidateLastUpdate(self):
    """Tests invalidate_last_update."""
    self.GenerateAppData('foo.json', appid='foo')
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS,
                     invalidate_last_update=True)
    request = GenerateXMLRequest([GenerateXMLAppRequest(appid='foo'),])
    response = neb.GetResponseToRequest(nebraska.Request(request))
    app = ElementTree.fromstring(response).find('app')
    self.assertEqual(app.attrib['appid'], 'foo')
    update_check = app.find('updatecheck')
    self.assertEqual(update_check.attrib['status'], 'noupdate')
    self.assertEqual(update_check.attrib['_invalidate_last_update'], 'true')


  def testEvent(self):
    """Tests event requests."""
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([
        GenerateXMLAppRequest(appid='foo', event=True, previous_version='1'),
        GenerateXMLAppRequest(appid='test', event=True, previous_version='1'),
    ])

    request = nebraska.Request(request)
    self.assertEqual(request.version, '1.0.0')

    response = neb.GetResponseToRequest(request)
    root = ElementTree.fromstring(response)
    apps = root.findall('app')
    self.assertEqual(len(apps), 2)
    for app in apps:
      event = app.find('event')
      self.assertEqual(event.attrib['status'], 'ok')

  def testPing(self):
    """Tests ping requests."""
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([
        GenerateXMLAppRequest(appid='foo', ping=True),
        GenerateXMLAppRequest(appid='test', ping=True),
    ])

    request = nebraska.Request(request)
    self.assertEqual(request.version, '1.0.0')

    response = neb.GetResponseToRequest(request)
    root = ElementTree.fromstring(response)

    apps = root.findall('app')
    self.assertEqual(len(apps), 2)
    for app in apps:
      ping = app.find('ping')
      self.assertEqual(ping.attrib['status'], 'ok')

  def testCriticalUpdate(self):
    """Tests correct response for critical updates."""
    self.GenerateAppData()
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([GenerateXMLAppRequest()])

    neb.UpdateConfig(critical_update=True)
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    action_tag = root.findall(
        'app/updatecheck/manifest/actions/action')[1]
    self.assertEqual(action_tag.attrib['deadline'], 'now')

  def testPublicKey(self):
    """Tests public key is included in the response."""
    app_data = self.GenerateAppData(include_public_key=True)
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([GenerateXMLAppRequest()])

    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    action_tag = root.findall(
        'app/updatecheck/manifest/actions/action')[1]
    self.assertEqual(action_tag.attrib['PublicKeyRsa'],
                     app_data.public_key)

  def testRollback(self,):
    """Tests rollback parametes are setup correctly."""
    self.GenerateAppData()
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([GenerateXMLAppRequest(rollback_allowed=True)])

    neb.UpdateConfig(is_rollback=True)
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    update_check_tag = root.find('app/updatecheck')
    index_strs = ['', '_0', '_1', '_2', '_3', '_4']
    self.assertEqual(update_check_tag.attrib['_is_rollback'], 'true')
    for idx in index_strs:
      self.assertEqual(update_check_tag.attrib['_firmware_version' + idx],
                       nebraska._FIRMWARE_VER)
      self.assertEqual(update_check_tag.attrib['_kernel_version' + idx],
                       nebraska._KERNEL_VER)

  def testFailuresPerUrl(self):
    """Tests response for number of failures allowed per URL."""
    self.GenerateAppData()
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([GenerateXMLAppRequest()])

    neb.UpdateConfig(failures_per_url=10)
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    action_tag = root.findall(
        'app/updatecheck/manifest/actions/action')[1]
    self.assertEqual(action_tag.attrib['MaxFailureCountPerUrl'], '10')

  def testDisablePayloadBackoff(self):
    """Tests disabling payload backoff on the client."""
    self.GenerateAppData()
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([GenerateXMLAppRequest()])

    neb.UpdateConfig(disable_payload_backoff=True)
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    action_tag = root.findall(
        'app/updatecheck/manifest/actions/action')[1]
    self.assertEqual(action_tag.attrib['DisablePayloadBackoff'], 'true')

  def testNumUrls(self):
    """Tests the number of URLs are passed correctly."""
    self.GenerateAppData()
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([GenerateXMLAppRequest()])

    neb.UpdateConfig(num_urls=2)
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    urls = root.findall('app/updatecheck/urls/url')
    self.assertEqual(len(urls), 2)

  def testEolDate(self):
    """Tests the EOL date are passed correctly."""
    self.GenerateAppData()
    neb = nebraska.Nebraska()
    neb.UpdateConfig(update_app_index=nebraska.AppIndex(self.tempdir),
                     update_payloads_address=_PAYLOADS_ADDRESS)
    request = GenerateXMLRequest([GenerateXMLAppRequest()])

    neb.UpdateConfig(eol_date=1000)
    response = neb.GetResponseToRequest(nebraska.Request(request))
    root = ElementTree.fromstring(response)
    update_check = root.find('app/updatecheck')
    self.assertEqual(update_check.attrib['_eol_date'], '1000')


if __name__ == '__main__':
  # Disable logging so it doesn't pollute the unit test output. Failures and
  # exceptions are still shown.
  logging.disable(logging.CRITICAL)

  unittest.main()
