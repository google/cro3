#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for autoupdate.py."""

from __future__ import print_function

import json
import shutil
import socket
import tempfile
import unittest

import mock
import cherrypy  # pylint: disable=import-error

import autoupdate

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
    self.test_board = 'test-board'
    self.build_root = tempfile.mkdtemp('autoupdate_build_root')
    self.latest_dir = '12345_af_12-a1'
    self.latest_verision = '12345_af_12'
    self.static_image_dir = tempfile.mkdtemp('autoupdate_static_dir')
    self.hostname = '%s:%s' % (socket.gethostname(), self.port)
    self.test_dict = {
        'version': 'ForcedUpdate',
        'track': 'test-channel',
        'board': self.test_board,
        'hwclass': 'test-hardware-class',
    }
    self.test_data = _TEST_REQUEST % self.test_dict
    self.payload = 'My payload'
    cherrypy.request.base = 'http://%s' % self.hostname
    common_util.MkDirP(self.static_image_dir)
    self._xbuddy = xbuddy.XBuddy(False,
                                 static_dir=self.static_image_dir)
    mock.patch.object(xbuddy.XBuddy, '_GetArtifact')

  def tearDown(self):
    shutil.rmtree(self.build_root)
    shutil.rmtree(self.static_image_dir)

  def _DummyAutoupdateConstructor(self, **kwargs):
    """Creates a dummy autoupdater.  Used to avoid using constructor."""
    dummy = autoupdate.Autoupdate(self._xbuddy,
                                  static_dir=self.static_image_dir,
                                  **kwargs)
    return dummy

  def testChangeUrlPort(self):
    # pylint: disable=protected-access
    r = autoupdate._ChangeUrlPort('http://fuzzy:8080/static', 8085)
    self.assertEqual(r, 'http://fuzzy:8085/static')

    r = autoupdate._ChangeUrlPort('http://fuzzy/static', 8085)
    self.assertEqual(r, 'http://fuzzy:8085/static')

    r = autoupdate._ChangeUrlPort('ftp://fuzzy/static', 8085)
    self.assertEqual(r, 'ftp://fuzzy:8085/static')

    r = autoupdate._ChangeUrlPort('ftp://fuzzy', 8085)
    self.assertEqual(r, 'ftp://fuzzy:8085')

  def testHandleHostInfoPing(self):
    au_mock = self._DummyAutoupdateConstructor()
    self.assertRaises(AssertionError, au_mock.HandleHostInfoPing, None)

    # Setup fake host_infos entry and ensure it comes back to us in one piece.
    test_ip = '1.2.3.4'
    au_mock.host_infos.GetInitHostInfo(test_ip).attrs = self.test_dict
    self.assertEqual(
        json.loads(au_mock.HandleHostInfoPing(test_ip)), self.test_dict)


if __name__ == '__main__':
  unittest.main()
