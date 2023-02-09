#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2014 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for cherrypy_ext."""

from __future__ import print_function

import tempfile
import unittest

import cherrypy  # pylint: disable=import-error
import cherrypy_ext
import mox  # pylint: disable=import-error


class CherrypyExtTest(mox.MoxTestBase):
    """Tests for the cherrypy_ext module."""

    def testPortFile(self):
        """Check that PortFile correctly reports a bound port."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            portfile = f.name
        bus = self.mox.CreateMock(cherrypy.engine)
        self.mox.StubOutWithMock(bus, "log")
        bus.log(mox.IsA(str)).MultipleTimes()

        cherrypy.server = self.mox.CreateMock(object)
        cherrypy.server.httpserver = self.mox.CreateMock(object)
        cherrypy.server.httpserver.socket = self.mox.CreateMock(object)
        cherrypy.server.httpserver.socket.getsockname = None
        self.mox.StubOutWithMock(
            cherrypy.server.httpserver.socket, "getsockname"
        )
        cherrypy.server.httpserver.socket.getsockname().AndReturn(None)
        cherrypy.server.httpserver.socket.getsockname().AndReturn(("", 55555))

        self.mox.ReplayAll()

        plugin = cherrypy_ext.PortFile(bus, portfile)
        plugin.start()  # Signal server start; no socket binding yet.
        with open(portfile) as f:
            self.assertEqual("", f.read())
        plugin.log("foo", 1)  # Emit a log signal; socket "bound" at this point.
        with open(portfile) as f:
            self.assertEqual("55555", f.read())

        self.mox.VerifyAll()


if __name__ == "__main__":
    unittest.main()
