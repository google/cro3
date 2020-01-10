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
    self.tempdir = tempfile.mkdtemp('tempdir')
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
    shutil.rmtree(self.tempdir)
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

  @mock.patch.object(autoupdate.Autoupdate, 'GetPathToPayload')
  def testHandleUpdatePing(self, path_to_payload_mock):
    """Tests HandleUpdatePing"""
    au_mock = self._DummyAutoupdateConstructor()
    path_to_payload_mock.return_value = self.tempdir
    request = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" delta_okay="true"
       track="stable-channel" board="eve">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
</request>"""

    self.assertIn('error-unknownApplication', au_mock.HandleUpdatePing(request))


class MaxUpdatesTableTest(unittest.TestCase):
  """Tests MaxUpdatesTable"""

  def testSessionTable(self):
    """Tests that SessionData() method correctly returns requested data."""
    table = autoupdate.SessionTable()
    g_data = {'foo': 0}

    table.SetSessionData('id-1', g_data)
    with table.SessionData('id-1') as data:
      data.update({'foo': data.get('foo') + 1})
    # Value of the global data should be increased by now.
    self.assertTrue(g_data['foo'], 1)

    # Increase again.
    with table.SessionData('id-1') as data:
      data.update({'foo': data.get('foo') + 1})
    self.assertTrue(g_data['foo'], 2)

    # Make sure multiple sessions can be set and used.
    g_data2 = {'foo': 10}
    table.SetSessionData('id-2', g_data2)
    with table.SessionData('id-2') as data:
      data.update({'foo': data.get('foo') + 1})
    self.assertTrue(g_data2['foo'], 11)

  def testNoneSession(self):
    """Tests if a session is not set, it should be returned as None."""
    table = autoupdate.SessionTable()
    # A session ID that has never been set should not return anything.
    with table.SessionData('foo-id') as data:
      self.assertDictEqual(data, {})

  def testOverrideSession(self):
    """Tests that a session can be overriden.."""
    table = autoupdate.SessionTable()

    table.SetSessionData('id-1', {'foo': 0})
    table.SetSessionData('id-1', {'bar': 1})
    with table.SessionData('id-1') as data:
      self.assertEqual(data.get('bar'), 1)

  @mock.patch.object(autoupdate.SessionTable, '_IsSessionExpired',
                     side_effect=lambda s: 'foo' in s.data)
  @mock.patch.object(autoupdate.SessionTable, '_ShouldPurge',
                     return_value=True)
  # pylint: disable=unused-argument
  def testPurge(self, p, ps):
    """Tests that data is being purged correctly."""
    table = autoupdate.SessionTable()

    table.SetSessionData('id-1', {'foo': 1})
    table.SetSessionData('id-2', {'bar': 2})

    # Set a random session to make _Purge() be called.
    table.SetSessionData('blah', {'blah': 1})
    # Only id-1 should be purged by now.
    with table.SessionData('id-1') as data:
      self.assertDictEqual(data, {})
    with table.SessionData('id-2') as data:
      self.assertDictEqual(data, {'bar': 2})


if __name__ == '__main__':
  unittest.main()
