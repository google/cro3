#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for autoupdate.py."""

import mox
import os
import unittest
import web

import autoupdate

_TEST_REQUEST = """
<client_test xmlns:o="http://www.google.com/update2/request" updaterversion="%(client)s" >
  <o:app version="%(version)s" track="%(track)s" board="%(board)s" />
  <o:updatecheck />
</client_test>"""


class AutoupdateTest(mox.MoxTestBase):
  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.mox.StubOutWithMock(autoupdate.Autoupdate, '_GetSize')
    self.mox.StubOutWithMock(autoupdate.Autoupdate, '_GetHash')
    self.mox.StubOutWithMock(autoupdate.Autoupdate, '_GetSHA256')
    self.mox.StubOutWithMock(autoupdate.Autoupdate, 'GetUpdatePayload')
    self.mox.StubOutWithMock(autoupdate.Autoupdate, '_GetLatestImageDir')
    self.test_board = 'test-board'
    self.build_root = '/src_path/build/images'
    self.latest_dir = '12345_af_12-a1'
    self.latest_verision = '12345_af_12'
    self.static_image_dir = '/tmp/static-dir/'
    self.hostname = 'fake-host'
    self.test_dict = { 'client': 'ChromeOSUpdateEngine-1.0',
                       'version': 'ForcedUpdate',
                       'track': 'unused_var',
                       'board': self.test_board
                     }
    self.test_data = _TEST_REQUEST % self.test_dict
    self.forced_image_path = '/path_to_force/chromiumos_image.bin'
    self.hash = 12345
    self.size = 54321
    self.url = 'http://%s/static/update.gz' % self.hostname
    self.payload = 'My payload'
    self.sha256 = 'SHA LA LA'

  def _DummyAutoupdateConstructor(self):
    """Creates a dummy autoupdater.  Used to avoid using constructor."""
    dummy = autoupdate.Autoupdate(root_dir=None,
                                  static_dir=self.static_image_dir)
    dummy.client_prefix = 'ChromeOSUpdateEngine'

    # Set to fool the web.
    web.ctx.host = self.hostname
    return dummy

  def testGenerateLatestUpdateImageWithForced(self):
    self.mox.StubOutWithMock(autoupdate.Autoupdate, 'GenerateUpdateImage')
    autoupdate.Autoupdate._GetLatestImageDir(self.test_board).AndReturn(
        '%s/%s/%s' % (self.build_root, self.test_board, self.latest_dir))
    autoupdate.Autoupdate.GenerateUpdateImage(
        '%s/%s/%s/chromiumos_image.bin' % (self.build_root, self.test_board,
                                           self.latest_dir),
        move_to_static_dir=True,
        static_image_dir=self.static_image_dir).AndReturn(True)

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    self.assertTrue(au_mock.GenerateLatestUpdateImage(self.test_board,
                                                      'ForcedUpdate',
                                                      self.static_image_dir))
    self.mox.VerifyAll()

  def testHandleUpdatePingForForcedImage(self):
    self.mox.StubOutWithMock(autoupdate.Autoupdate, 'GenerateUpdateImage')

    test_data = _TEST_REQUEST % self.test_dict

    autoupdate.Autoupdate.GenerateUpdateImage(
        self.forced_image_path,
        move_to_static_dir=True,
        static_image_dir=self.static_image_dir).AndReturn(True)
    autoupdate.Autoupdate._GetHash(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.hash)
    autoupdate.Autoupdate._GetSHA256(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.sha256)
    autoupdate.Autoupdate._GetSize(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.size)
    autoupdate.Autoupdate.GetUpdatePayload(
        self.hash, self.sha256, self.size, self.url).AndReturn(self.payload)

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    au_mock.forced_image = self.forced_image_path
    self.assertEqual(au_mock.HandleUpdatePing(test_data), self.payload)
    self.mox.VerifyAll()

  def testHandleUpdatePingForLatestImage(self):
    self.mox.StubOutWithMock(autoupdate.Autoupdate, 'GenerateLatestUpdateImage')

    test_data = _TEST_REQUEST % self.test_dict

    autoupdate.Autoupdate.GenerateLatestUpdateImage(
        self.test_board, 'ForcedUpdate', self.static_image_dir).AndReturn(True)
    autoupdate.Autoupdate._GetHash(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.hash)
    autoupdate.Autoupdate._GetSHA256(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.sha256)
    autoupdate.Autoupdate._GetSize(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.size)
    autoupdate.Autoupdate.GetUpdatePayload(
        self.hash, self.sha256, self.size, self.url).AndReturn(self.payload)

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    self.assertEqual(au_mock.HandleUpdatePing(test_data), self.payload)
    self.mox.VerifyAll()

  def testHandleUpdatePingForArchivedBuild(self):
    self.mox.StubOutWithMock(autoupdate.Autoupdate, 'GenerateImageFromZip')

    test_data = _TEST_REQUEST % self.test_dict

    autoupdate.Autoupdate.GenerateImageFromZip(
        self.static_image_dir).AndReturn(True)
    autoupdate.Autoupdate._GetHash(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.hash)
    autoupdate.Autoupdate._GetSHA256(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.sha256)
    autoupdate.Autoupdate._GetSize(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.size)
    autoupdate.Autoupdate.GetUpdatePayload(
        self.hash, self.sha256, self.size,
        'http://%s/static/archive/update.gz' % self.hostname).AndReturn(
            self.payload)

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    au_mock.serve_only = True
    au_mock.static_urlbase = 'http://%s/static/archive' % self.hostname
    self.assertEqual(au_mock.HandleUpdatePing(test_data), self.payload)
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
