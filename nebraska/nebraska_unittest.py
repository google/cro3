#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittests for Nebraska server"""

from __future__ import print_function

import mock
import unittest

import nebraska

_NEBRASKA_PORT = 11235


class NebraskaHandler(nebraska.NebraskaHandler):
  """Subclass NebraskaHandler to facilitate testing

  Because of the complexity of the socket handling super class init functions,
  the easiest way to test NebraskaHandler is to just subclass it and mock
  whatever we need from its superclasses.
  """
  # pylint: disable=super-init-not-called
  def __init__(self):
    self.headers = None
    self.rfile = None


def NebraskaGenerator(port):
  return nebraska.NebraskaServer(port)


class NebraskaHandlerTest(unittest.TestCase):
  """Test NebraskaHandler"""

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

  def testDoPost(self):
    """Test do_POST."""
    nebraska_handler = NebraskaHandler()
    nebraska_handler.headers = mock.MagicMock()
    nebraska_handler.rfile = mock.MagicMock()
    nebraska_handler.rfile.read.return_value = "foobar"
    nebraska_handler.send_error = mock.MagicMock()

    nebraska_handler.do_POST()
    nebraska_handler.send_error.assert_called_once_with(500, "foobar")


class NebraskaServerTest(unittest.TestCase):
  """Test NebraskaServer"""

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
