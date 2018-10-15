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


class NebraskaHandlerTest(unittest.TestCase):
  """Test NebraskaHandler."""

  def testGetRequestString(self):
    """Test GetRequestString."""
    nebraska_handler = NebraskaHandler()
    nebraska_handler.headers = mock.MagicMock()
    nebraska_handler.rfile = mock.MagicMock()
    nebraska_handler.headers.getheader.return_value = 42
    nebraska_handler.rfile.read.return_value = "foobar"

    result = nebraska_handler.GetRequestString()

    nebraska_handler.headers.getheader.assert_called_once_with('content-length')
    nebraska_handler.rfile.read.assert_called_once_with(42)
    self.assertTrue(result == "foobar")

  def testDoPostSuccess(self):
    """Test do_POST success."""

    nebraska_handler = NebraskaHandler()

    with mock.patch('nebraska.Request') as request_mock:
      nebraska_handler.GetRequestString = mock.MagicMock(return_value="foo")
      nebraska_handler.send_error = mock.MagicMock()
      request_instance = request_mock.return_value

      nebraska_handler.do_POST()
      request_mock.assert_called_once_with("foo")
      request_instance.ParseRequest.assert_called_once()
      nebraska_handler.send_error.assert_called_once_with(
          500, "Not implemented!")

  def testDoPostInvalidRequest(self):
    """Test do_POST invalid request."""

    nebraska_handler = NebraskaHandler()

    with mock.patch('nebraska.Request') as request_mock:
      request_mock.return_value.ParseRequest.side_effect = ValueError()

      nebraska_handler.GetRequestString = mock.MagicMock()
      nebraska_handler.send_error = mock.MagicMock()

      nebraska_handler.do_POST()

      nebraska_handler.send_error.assert_called_once_with(
          400, "Invalid update or install request")


class NebraskaServerTest(unittest.TestCase):
  """Test NebraskaServer."""

  def testStart(self):
    """Test Start"""
    server = nebraska.NebraskaServer(_NEBRASKA_PORT)

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
    """Test Stop"""
    nebraska_server = NebraskaGenerator(_NEBRASKA_PORT)

    # pylint: disable=protected-access
    nebraska_server._httpd = mock.MagicMock(name="_httpd")
    nebraska_server._server_thread = mock.MagicMock(name="_server_thread")
    nebraska_server.Stop()
    # pylint: disable=protected-access
    nebraska_server._httpd.shutdown.assert_called_once_with()
    nebraska_server._server_thread.join.assert_called_once_with()


if __name__ == '__main__':
  unittest.main()
