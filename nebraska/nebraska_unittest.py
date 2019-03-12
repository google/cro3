#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittests for Nebraska server."""

from __future__ import print_function

import mock
import unittest

import nebraska

_NEBRASKA_PORT = 11235
_INSTALL_DIR = "test_install_dir"
_UPDATE_DIR = "test_update_dir"
_PAYLOAD_ADDRESS = "111.222.212:2357"

class MockNebraskaHandler(nebraska.NebraskaHandler):
  """Subclass NebraskaHandler to facilitate testing.

  Because of the complexity of the socket handling super class init functions,
  the easiest way to test NebraskaHandler is to just subclass it and mock
  whatever we need from its super classes.
  """
  # pylint: disable=super-init-not-called
  def __init__(self):
    self.headers = mock.MagicMock()
    self.send_response = mock.MagicMock()
    self.send_error = mock.MagicMock()
    self.send_header = mock.MagicMock()
    self.end_headers = mock.MagicMock()
    self.rfile = mock.MagicMock()
    self.wfile = mock.MagicMock()
    self.server = mock.MagicMock()
    self.server.owner = nebraska.NebraskaServer(nebraska.Nebraska(
        _PAYLOAD_ADDRESS, _PAYLOAD_ADDRESS))


class NebraskaTest(unittest.TestCase):
  """Test Nebraska."""

  def testDefaultInstallPayloadsAddress(self):
    """Tests the default install_payloads_address is correctly set."""
    update_addr = 'foo/update'
    install_addr = 'foo/install'
    # pylint: disable=protected-access
    n = nebraska.Nebraska(update_addr, install_addr)
    self.assertEqual(n._install_payloads_address, install_addr)

    n = nebraska.Nebraska(update_addr)
    self.assertEqual(n._install_payloads_address, update_addr)

class NebraskaHandlerTest(unittest.TestCase):
  """Test NebraskaHandler."""

  def testDoPostSuccess(self):
    """Tests do_POST success."""
    nebraska_handler = MockNebraskaHandler()
    test_response = "foobar"

    with mock.patch('nebraska.Response') as response_mock:
      response_instance = response_mock.return_value
      response_instance.GetXMLString.return_value = test_response
      nebraska_handler.do_POST()

    nebraska_handler.send_response.assert_called_once_with(200)
    nebraska_handler.send_header.assert_called_once()
    nebraska_handler.end_headers.assert_called_once()
    nebraska_handler.wfile.write.assert_called_once_with(test_response)

  def testDoPostInvalidRequest(self):
    """Test do_POST invalid request."""

    nebraska_handler = MockNebraskaHandler()

    with mock.patch('nebraska.Response') as response_mock:
      response_mock.side_effect = ValueError

      nebraska_handler.do_POST()

      nebraska_handler.send_error.assert_called_once_with(
          500, "Failed to handle incoming request")

  def testDoPostInvalidResponse(self):
    """Tests do_POST invalid response handling."""

    nebraska_handler = MockNebraskaHandler()

    with mock.patch('nebraska.traceback') as traceback_mock:
      with mock.patch('nebraska.Response') as response_mock:
        response_instance = response_mock.return_value
        response_instance.GetXMLString.side_effect = Exception
        nebraska_handler.do_POST()
        traceback_mock.print_exc.assert_called_once()
        nebraska_handler.send_error.assert_called_once_with(
            500, "Failed to handle incoming request")

class NebraskaServerTest(unittest.TestCase):
  """Test NebraskaServer."""

  def testStart(self):
    """Tests Start."""
    nebraska_instance = nebraska.Nebraska(_PAYLOAD_ADDRESS, _PAYLOAD_ADDRESS)
    server = nebraska.NebraskaServer(nebraska_instance, _NEBRASKA_PORT)

    with mock.patch('nebraska.HTTPServer') as server_mock:
      with mock.patch('nebraska.threading.Thread') as thread_mock:
        server.Start()

        server_mock.assert_called_once_with(
            ('', _NEBRASKA_PORT), nebraska.NebraskaHandler)

        # pylint: disable=protected-access
        thread_mock.assert_has_calls((
            mock.call(target=server._httpd.serve_forever),
            mock.call().start()))

  def testStop(self):
    """Tests Stop."""
    nebraska_instance = nebraska.Nebraska(
        _PAYLOAD_ADDRESS, _PAYLOAD_ADDRESS)
    server = nebraska.NebraskaServer(nebraska_instance, _NEBRASKA_PORT)

    # pylint: disable=protected-access
    server._httpd = mock.MagicMock(name="_httpd")
    server._server_thread = mock.MagicMock(name="_server_thread")
    server.Stop()
    # pylint: disable=protected-access
    server._httpd.shutdown.assert_called_once_with()
    server._server_thread.join.assert_called_once_with()


if __name__ == '__main__':
  unittest.main()
