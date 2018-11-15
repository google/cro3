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
from unittest_common import NebraskaHandler, NebraskaGenerator

_NEBRASKA_PORT = 11235
_INSTALL_DIR = "test_install_dir"
_UPDATE_DIR = "test_update_dir"
_PAYLOAD_ADDR = "111.222.212:2357"


class NebraskaHandlerTest(unittest.TestCase):
  """Test NebraskaHandler."""

  def testDoPostSuccess(self):
    """Tests do_POST success."""
    nebraska_handler = NebraskaHandler()
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

    nebraska_handler = NebraskaHandler()

    with mock.patch('nebraska.Response') as response_mock:
      response_mock.side_effect = ValueError

      nebraska_handler.do_POST()

      nebraska_handler.send_error.assert_called_once_with(
          500, "Failed to handle incoming request")

  def testDoPostInvalidResponse(self):
    """Tests do_POST invalid response handling."""

    nebraska_handler = NebraskaHandler()

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
    server = nebraska.NebraskaServer(
        _INSTALL_DIR, _UPDATE_DIR, _PAYLOAD_ADDR, _NEBRASKA_PORT)

    with mock.patch('nebraska.HTTPServer') as server_mock:
      with mock.patch('nebraska.threading.Thread') as thread_mock:
        server.install_index = mock.MagicMock()
        server.update_index = mock.MagicMock()

        server.Start()

        server_mock.assert_called_once_with(
            ('', _NEBRASKA_PORT), nebraska.NebraskaHandler)

        # pylint: disable=protected-access
        thread_mock.assert_has_calls((
            mock.call(target=server._httpd.serve_forever),
            mock.call().start()))

        server.install_index.Scan.assert_called_once()
        server.update_index.Scan.assert_called_once()

  def testStop(self):
    """Tests Stop."""
    nebraska_server = NebraskaGenerator(
        _PAYLOAD_ADDR, _UPDATE_DIR, _INSTALL_DIR, _NEBRASKA_PORT)

    # pylint: disable=protected-access
    nebraska_server._httpd = mock.MagicMock(name="_httpd")
    nebraska_server._server_thread = mock.MagicMock(name="_server_thread")
    nebraska_server.Stop()
    # pylint: disable=protected-access
    nebraska_server._httpd.shutdown.assert_called_once_with()
    nebraska_server._server_thread.join.assert_called_once_with()


if __name__ == '__main__':
  unittest.main()
