#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for autoupdate.py."""

import cherrypy
import json
import mox
import os
import socket
import unittest

import autoupdate

_TEST_REQUEST = """
<client_test xmlns:o="http://www.google.com/update2/request" updaterversion="%(client)s" >
  <o:app version="%(version)s" track="%(track)s" board="%(board)s" />
  <o:updatecheck />
  <o:event eventresult="%(event_result)d" eventtype="%(event_type)d" />
</client_test>"""


class AutoupdateTest(mox.MoxTestBase):
  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.mox.StubOutWithMock(autoupdate.Autoupdate, '_GetSize')
    self.mox.StubOutWithMock(autoupdate.Autoupdate, '_GetHash')
    self.mox.StubOutWithMock(autoupdate.Autoupdate, '_GetSHA256')
    self.mox.StubOutWithMock(autoupdate.Autoupdate, 'GetUpdatePayload')
    self.mox.StubOutWithMock(autoupdate.Autoupdate, '_GetLatestImageDir')
    self.port = 8080
    self.test_board = 'test-board'
    self.build_root = '/src_path/build/images'
    self.latest_dir = '12345_af_12-a1'
    self.latest_verision = '12345_af_12'
    self.static_image_dir = '/tmp/static-dir/'
    self.hostname = '%s:%s' % (socket.gethostname(), self.port)
    self.test_dict = {
        'client': 'ChromeOSUpdateEngine-1.0',
        'version': 'ForcedUpdate',
        'track': 'unused_var',
        'board': self.test_board,
        'event_result': 2,
        'event_type': 3
    }
    self.test_data = _TEST_REQUEST % self.test_dict
    self.forced_image_path = '/path_to_force/chromiumos_image.bin'
    self.hash = 12345
    self.size = 54321
    self.url = 'http://%s/static/update.gz' % self.hostname
    self.payload = 'My payload'
    self.sha256 = 'SHA LA LA'
    cherrypy.request.base = 'http://%s' % self.hostname

  def _DummyAutoupdateConstructor(self):
    """Creates a dummy autoupdater.  Used to avoid using constructor."""
    dummy = autoupdate.Autoupdate(root_dir=None,
                                  static_dir=self.static_image_dir,
                                  port=self.port)
    dummy.client_prefix = 'ChromeOSUpdateEngine'
    return dummy

  def testGetRightSignedDeltaPayloadDir(self):
    """Test that our directory is what we expect it to be for signed updates."""
    self.mox.StubOutWithMock(autoupdate.Autoupdate, '_GetMd5')
    key_path = 'test_key_path'
    src_image = 'test_src_image'
    target_image = 'test_target_image'
    hashes = ['12345', '67890', 'abcde']

    autoupdate.Autoupdate._GetMd5(target_image).AndReturn(hashes[1])
    autoupdate.Autoupdate._GetMd5(src_image).AndReturn(hashes[0])
    autoupdate.Autoupdate._GetMd5(key_path).AndReturn(hashes[2])

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    au_mock.private_key = key_path
    update_dir = au_mock.FindCachedUpdateImageSubDir(src_image, target_image)
    self.assertEqual(os.path.basename(update_dir), '%s_%s+%s' % tuple(hashes))
    self.mox.VerifyAll()

  def testGenerateLatestUpdateImageWithForced(self):
    self.mox.StubOutWithMock(autoupdate.Autoupdate,
                             'GenerateUpdateImageWithCache')
    autoupdate.Autoupdate._GetLatestImageDir(self.test_board).AndReturn(
        '%s/%s/%s' % (self.build_root, self.test_board, self.latest_dir))
    autoupdate.Autoupdate.GenerateUpdateImageWithCache(
        '%s/%s/%s/chromiumos_image.bin' % (self.build_root, self.test_board,
                                           self.latest_dir),
        static_image_dir=self.static_image_dir).AndReturn('update.gz')

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    self.assertTrue(au_mock.GenerateLatestUpdateImage(self.test_board,
                                                      'ForcedUpdate',
                                                      self.static_image_dir))
    self.mox.VerifyAll()

  def testHandleUpdatePingForForcedImage(self):
    self.mox.StubOutWithMock(autoupdate.Autoupdate,
                             'GenerateUpdateImageWithCache')

    test_data = _TEST_REQUEST % self.test_dict

    autoupdate.Autoupdate.GenerateUpdateImageWithCache(
        self.forced_image_path,
        static_image_dir=self.static_image_dir).AndReturn('update.gz')
    autoupdate.Autoupdate._GetHash(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.hash)
    autoupdate.Autoupdate._GetSHA256(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.sha256)
    autoupdate.Autoupdate._GetSize(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.size)
    autoupdate.Autoupdate.GetUpdatePayload(
        self.hash, self.sha256, self.size, self.url, False).AndReturn(
            self.payload)

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    au_mock.forced_image = self.forced_image_path
    self.assertEqual(au_mock.HandleUpdatePing(test_data), self.payload)
    self.mox.VerifyAll()

  def testHandleUpdatePingForLatestImage(self):
    self.mox.StubOutWithMock(autoupdate.Autoupdate, 'GenerateLatestUpdateImage')

    test_data = _TEST_REQUEST % self.test_dict

    autoupdate.Autoupdate.GenerateLatestUpdateImage(
        self.test_board, 'ForcedUpdate', self.static_image_dir).AndReturn(
            'update.gz')
    autoupdate.Autoupdate._GetHash(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.hash)
    autoupdate.Autoupdate._GetSHA256(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.sha256)
    autoupdate.Autoupdate._GetSize(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.size)
    autoupdate.Autoupdate.GetUpdatePayload(
        self.hash, self.sha256, self.size, self.url, False).AndReturn(
            self.payload)

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    self.assertEqual(au_mock.HandleUpdatePing(test_data), self.payload)
    self.assertEqual(
        au_mock.host_info['127.0.0.1']['last_known_version'], 'ForcedUpdate')
    self.assertEqual(
        au_mock.host_info['127.0.0.1']['last_event_type'],
        self.test_dict['event_type'])
    self.assertEqual(
        au_mock.host_info['127.0.0.1']['last_event_status'],
        self.test_dict['event_result'])
    self.mox.VerifyAll()

  def testChangeUrlPort(self):
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

    # Setup fake host_info entry and ensure it comes back to us in one piece.
    test_ip = '1.2.3.4'
    au_mock.host_info[test_ip] = self.test_dict
    self.assertEqual(
        json.loads(au_mock.HandleHostInfoPing(test_ip)), self.test_dict)

  def testHandleSetUpdatePing(self):
    au_mock = self._DummyAutoupdateConstructor()
    test_ip = '1.2.3.4'
    test_label = 'test/old-update'
    self.assertRaises(
        AssertionError, au_mock.HandleSetUpdatePing, test_ip, None)
    self.assertRaises(
        AssertionError, au_mock.HandleSetUpdatePing, None, test_label)
    self.assertRaises(
        AssertionError, au_mock.HandleSetUpdatePing, None, None)

    au_mock.HandleSetUpdatePing(test_ip, test_label)
    self.assertEqual(
        au_mock.host_info[test_ip]['forced_update_label'], test_label)

  def testHandleUpdatePingWithSetUpdate(self):
    self.mox.StubOutWithMock(autoupdate.Autoupdate, 'GenerateLatestUpdateImage')

    test_data = _TEST_REQUEST % self.test_dict
    test_label = 'new_update-test/the-new-update'
    new_image_dir = os.path.join(self.static_image_dir, test_label)
    new_url = self.url.replace('update.gz', test_label + '/update.gz')

    autoupdate.Autoupdate.GenerateLatestUpdateImage(
        self.test_board, 'ForcedUpdate', new_image_dir).AndReturn(
            'update.gz')
    autoupdate.Autoupdate._GetHash(os.path.join(
        new_image_dir, 'update.gz')).AndReturn(self.hash)
    autoupdate.Autoupdate._GetSHA256(os.path.join(
        new_image_dir, 'update.gz')).AndReturn(self.sha256)
    autoupdate.Autoupdate._GetSize(os.path.join(
        new_image_dir, 'update.gz')).AndReturn(self.size)
    autoupdate.Autoupdate.GetUpdatePayload(
        self.hash, self.sha256, self.size, new_url, False).AndReturn(
            self.payload)

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    au_mock.HandleSetUpdatePing('127.0.0.1', test_label)
    self.assertEqual(
        au_mock.host_info['127.0.0.1']['forced_update_label'], test_label)
    self.assertEqual(au_mock.HandleUpdatePing(test_data), self.payload)
    self.assertFalse('forced_update_label' in au_mock.host_info['127.0.0.1'])


if __name__ == '__main__':
  unittest.main()
