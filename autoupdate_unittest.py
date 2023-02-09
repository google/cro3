#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2010 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for autoupdate.py."""

from __future__ import print_function

import shutil
import socket
import tempfile
import unittest
import unittest.mock as mock

import autoupdate
import cherrypy  # pylint: disable=import-error
import setup_chromite  # pylint: disable=unused-import

from chromite.lib.xbuddy import common_util
from chromite.lib.xbuddy import xbuddy


_TEST_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0" updater="ChromeOSUpdateEngine" updaterversion="0.1.0.0">
  <app appid="test-appid" version="%(version)s" track="%(track)s"
       board="%(board)s" hardware_class="%(hwclass)s">
    <updatecheck />
  </app>
</request>"""


class AutoupdateTest(unittest.TestCase):
    """Tests for the autoupdate.Autoupdate class."""

    def setUp(self):
        self.port = 8080
        self.test_board = "test-board"
        self.build_root = tempfile.mkdtemp("autoupdate_build_root")
        self.tempdir = tempfile.mkdtemp("tempdir")
        self.latest_dir = "12345_af_12-a1"
        self.latest_verision = "12345_af_12"
        self.static_image_dir = tempfile.mkdtemp("autoupdate_static_dir")
        self.hostname = "%s:%s" % (socket.gethostname(), self.port)
        self.test_dict = {
            "version": "ForcedUpdate",
            "track": "test-channel",
            "board": self.test_board,
            "hwclass": "test-hardware-class",
        }
        self.test_data = _TEST_REQUEST % self.test_dict
        self.payload = "My payload"
        cherrypy.request.base = "http://%s" % self.hostname
        common_util.MkDirP(self.static_image_dir)
        self._xbuddy = xbuddy.XBuddy(False, static_dir=self.static_image_dir)
        mock.patch.object(xbuddy.XBuddy, "_GetArtifact")

    def tearDown(self):
        shutil.rmtree(self.build_root)
        shutil.rmtree(self.tempdir)
        shutil.rmtree(self.static_image_dir)

    def _DummyAutoupdateConstructor(self, **kwargs):
        """Creates a dummy autoupdater.  Used to avoid using constructor."""
        dummy = autoupdate.Autoupdate(
            self._xbuddy, static_dir=self.static_image_dir, **kwargs
        )
        return dummy

    def testChangeUrlPort(self):
        # pylint: disable=protected-access
        r = autoupdate._ChangeUrlPort("http://fuzzy:8080/static", 8085)
        self.assertEqual(r, "http://fuzzy:8085/static")

        r = autoupdate._ChangeUrlPort("http://fuzzy/static", 8085)
        self.assertEqual(r, "http://fuzzy:8085/static")

        r = autoupdate._ChangeUrlPort("ftp://fuzzy/static", 8085)
        self.assertEqual(r, "ftp://fuzzy:8085/static")

        r = autoupdate._ChangeUrlPort("ftp://fuzzy", 8085)
        self.assertEqual(r, "ftp://fuzzy:8085")

    @mock.patch.object(autoupdate.Autoupdate, "GetBuildID")
    def testHandleUpdatePing(self, get_build_id):
        """Tests HandleUpdatePing"""
        au_mock = self._DummyAutoupdateConstructor()
        get_build_id.return_value = ""
        request = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" delta_okay="true"
       track="stable-channel" board="eve">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
</request>"""

        self.assertIn(
            b'<updatecheck status="noupdate"', au_mock.HandleUpdatePing(request)
        )


if __name__ == "__main__":
    unittest.main()
