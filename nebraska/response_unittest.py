#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittests for responses sent by the Nebraska server."""

from __future__ import print_function

import mock
import unittest

from xml.etree import ElementTree

import nebraska
import unittest_common

# pylint: disable=protected-access

_UPDATE_PAYLOADS_ADDRESS = 'www.google.com/update'
_INSTALL_PAYLOADS_ADDRESS = 'www.google.com/install'

class ResponseTest(unittest.TestCase):
  """Tests for Response class."""

  def testGetXMLStringSuccess(self):
    """Tests GetXMLString success."""
    properties = nebraska.NebraskaProperties(
        _UPDATE_PAYLOADS_ADDRESS,
        _INSTALL_PAYLOADS_ADDRESS,
        nebraska.AppIndex(mock.MagicMock()),
        nebraska.AppIndex(mock.MagicMock()))

    app_list = (
        unittest_common.GenerateAppData(is_delta=True, source_version='0.9.0'),
        unittest_common.GenerateAppData(appid='bar', is_delta=True,
                                        source_version='1.9.0'),
        unittest_common.GenerateAppData(appid='foobar'))
    properties.update_app_index._index = app_list

    request = mock.MagicMock()
    request.app_requests = [
        unittest_common.GenerateAppRequest(
            request_type=nebraska.Request.RequestType.UPDATE,
            appid='foo',
            ping=True,
            delta_okay=False),
        unittest_common.GenerateAppRequest(
            request_type=nebraska.Request.RequestType.UPDATE,
            appid='bar',
            ping=True,
            delta_okay=False),
        unittest_common.GenerateAppRequest(
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


class AppResponseTest(unittest.TestCase):
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
    app_request = unittest_common.GenerateAppRequest()
    match = unittest_common.GenerateAppData()
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
    app_request = unittest_common.GenerateAppRequest(
        request_type=nebraska.Request.RequestType.INSTALL)
    match = unittest_common.GenerateAppData()
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
    app_request = unittest_common.GenerateAppRequest()
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
    app_request = unittest_common.GenerateAppRequest(
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
    app_request = unittest_common.GenerateAppRequest()
    match = unittest_common.GenerateAppData()
    self._properties.update_app_index.Find.return_value = match
    self._properties.update_app_index.Contains.return_value = True
    self._properties.no_update = True

    response = nebraska.Response.AppResponse(
        app_request, self._properties).Compile()
    update_check_tag = response.findall('updatecheck')[0]
    self.assertTrue(update_check_tag.attrib['status'] == 'noupdate')

  def testAppResponsePing(self):
    """Tests AppResponse generation for no-op with a ping request."""
    app_request = unittest_common.GenerateAppRequest(
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
    app_request = unittest_common.GenerateAppRequest(
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
    app_request = unittest_common.GenerateAppRequest(
        request_type=nebraska.Request.RequestType.INSTALL)
    match = unittest_common.GenerateAppData()
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
    app_request = unittest_common.GenerateAppRequest()
    match = unittest_common.GenerateAppData()
    self._properties.update_app_index.Find.return_value = match
    self._properties.critical_update = True
    response = nebraska.Response.AppResponse(
        app_request, self._properties).Compile()
    action_tag = response.findall(
        'updatecheck/manifest/actions/action')[1]
    self.assertTrue(action_tag.attrib['deadline'] == 'now')

  def testPublicKey(self):
    """Tests public key is included in the response."""
    app_request = unittest_common.GenerateAppRequest()
    match = unittest_common.GenerateAppData(include_public_key=True)
    self._properties.update_app_index.Find.return_value = match
    response = nebraska.Response.AppResponse(
        app_request, self._properties).Compile()
    action_tag = response.findall(
        'updatecheck/manifest/actions/action')[1]
    self.assertTrue(action_tag.attrib['PublicKeyRsa'] == match.public_key)


if __name__ == '__main__':
  unittest.main()
