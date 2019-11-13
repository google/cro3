#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for cherrypy_ext."""

from __future__ import print_function

import tempfile
import unittest

import mox  # pylint: disable=import-error
import cherrypy  # pylint: disable=import-error

import cherrypy_ext


class CherrypyExtTest(mox.MoxTestBase):
  """Tests for the cherrypy_ext module."""

  def testPortFile(self):
    """Check that PortFile correctly reports a bound port."""
    with tempfile.NamedTemporaryFile(delete=False) as f:
      portfile = f.name
    bus = self.mox.CreateMock(cherrypy.engine)
    self.mox.StubOutWithMock(bus, 'log')
    bus.log(mox.IsA(str)).MultipleTimes()

    cherrypy.server = self.mox.CreateMock(object)
    cherrypy.server.httpserver = self.mox.CreateMock(object)
    cherrypy.server.httpserver.socket = self.mox.CreateMock(object)
    cherrypy.server.httpserver.socket.getsockname = None
    self.mox.StubOutWithMock(cherrypy.server.httpserver.socket, 'getsockname')
    cherrypy.server.httpserver.socket.getsockname().AndReturn(None)
    cherrypy.server.httpserver.socket.getsockname().AndReturn(('', 55555))

    self.mox.ReplayAll()

    plugin = cherrypy_ext.PortFile(bus, portfile)
    plugin.start()  # Signal server start; no socket binding yet.
    with open(portfile) as f:
      self.assertEqual('', f.read())
    plugin.log('foo', 1)  # Emit a log signal; socket "bound" at this point.
    with open(portfile) as f:
      self.assertEqual('55555', f.read())

    self.mox.VerifyAll()

  def testZeroPortPatcherSuccess(self):
    """Make sure that ZeroPatcher successfully patches CherryPy.

    This merely ensures that the patcher applies cleanly to the CherryPy
    version available to the test environment, giving us some assurance that
    it's still compatible with the range of versions that we might be using it
    with.  The actual testing of the arbitrary port binding feature is covered
    by integration tests.
    """
    self.assertIsNone(cherrypy_ext.ZeroPortPatcher.DoPatch(cherrypy))

  def testZeroPortPatcherFailure(self):
    """Make sure that ZeroPatcher fails with an incompatible CherryPy.

    This ensures that the patcher fails when applied to a CherryPy version that
    does not have the desired properties.
    """
    module = cherrypy.process.servers
    func_name = 'wait_for_free_port'
    orig_func = getattr(module, func_name, None)
    self.assertTrue(orig_func)
    delattr(module, func_name)
    self.assertRaises(AttributeError, cherrypy_ext.ZeroPortPatcher.DoPatch,
                      cherrypy)
    setattr(module, func_name, orig_func)


if __name__ == '__main__':
  unittest.main()
