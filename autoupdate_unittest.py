#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for autoupdate.py."""

import json
import os
import socket
import unittest

import cherrypy
import mox

import autoupdate
import common_util


_TEST_REQUEST = """
<client_test xmlns:o="http://www.google.com/update2/request" updaterversion="%(client)s" >
  <o:app version="%(version)s" track="%(track)s" board="%(board)s" />
  <o:updatecheck />
  <o:event eventresult="%(event_result)d" eventtype="%(event_type)d" />
</client_test>"""


class AutoupdateTest(mox.MoxTestBase):
  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.mox.StubOutWithMock(common_util, 'GetFileSize')
    self.mox.StubOutWithMock(common_util, 'GetFileSha1')
    self.mox.StubOutWithMock(common_util, 'GetFileSha256')
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
    return dummy

  def testGetRightSignedDeltaPayloadDir(self):
    """Test that our directory is what we expect it to be for signed updates."""
    self.mox.StubOutWithMock(common_util, 'GetFileMd5')
    key_path = 'test_key_path'
    src_image = 'test_src_image'
    target_image = 'test_target_image'
    src_hash = '12345'
    target_hash = '67890'
    key_hash = 'abcde'

    common_util.GetFileMd5(src_image).AndReturn(src_hash)
    common_util.GetFileMd5(target_image).AndReturn(target_hash)
    common_util.GetFileMd5(key_path).AndReturn(key_hash)

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    au_mock.private_key = key_path
    update_dir = au_mock.FindCachedUpdateImageSubDir(src_image, target_image)
    self.assertEqual(os.path.basename(update_dir),
                     '%s_%s+%s+patched_kernel' %
                     (src_hash, target_hash, key_hash))
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
    common_util.GetFileSha1(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.hash)
    common_util.GetFileSha256(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.sha256)
    common_util.GetFileSize(os.path.join(
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
    common_util.GetFileSha1(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.hash)
    common_util.GetFileSha256(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.sha256)
    common_util.GetFileSize(os.path.join(
        self.static_image_dir, 'update.gz')).AndReturn(self.size)
    autoupdate.Autoupdate.GetUpdatePayload(
        self.hash, self.sha256, self.size, self.url, False).AndReturn(
            self.payload)

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    self.assertEqual(au_mock.HandleUpdatePing(test_data), self.payload)
    curr_host_info = au_mock.host_infos.GetHostInfo('127.0.0.1');
    self.assertEqual(curr_host_info.GetAttr('last_known_version'),
                     'ForcedUpdate')
    self.assertEqual(curr_host_info.GetAttr('last_event_type'),
                     self.test_dict['event_type'])
    self.assertEqual(curr_host_info.GetAttr('last_event_status'),
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

    # Setup fake host_infos entry and ensure it comes back to us in one piece.
    test_ip = '1.2.3.4'
    au_mock.host_infos.GetInitHostInfo(test_ip).attrs = self.test_dict
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
        au_mock.host_infos.GetHostInfo(test_ip).GetAttr('forced_update_label'),
        test_label)

  def testHandleUpdatePingWithSetUpdate(self):
    self.mox.StubOutWithMock(autoupdate.Autoupdate, 'GenerateLatestUpdateImage')

    test_data = _TEST_REQUEST % self.test_dict
    test_label = 'new_update-test/the-new-update'
    new_image_dir = os.path.join(self.static_image_dir, test_label)
    new_url = self.url.replace('update.gz', test_label + '/update.gz')

    autoupdate.Autoupdate.GenerateLatestUpdateImage(
        self.test_board, 'ForcedUpdate', new_image_dir).AndReturn(
            'update.gz')
    common_util.GetFileSha1(os.path.join(
        new_image_dir, 'update.gz')).AndReturn(self.hash)
    common_util.GetFileSha256(os.path.join(
        new_image_dir, 'update.gz')).AndReturn(self.sha256)
    common_util.GetFileSize(os.path.join(
        new_image_dir, 'update.gz')).AndReturn(self.size)
    autoupdate.Autoupdate.GetUpdatePayload(
        self.hash, self.sha256, self.size, new_url, False).AndReturn(
            self.payload)

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    au_mock.HandleSetUpdatePing('127.0.0.1', test_label)
    self.assertEqual(
        au_mock.host_infos.GetHostInfo('127.0.0.1').
        GetAttr('forced_update_label'),
        test_label)
    self.assertEqual(au_mock.HandleUpdatePing(test_data), self.payload)
    self.assertFalse('forced_update_label' in
        au_mock.host_infos.GetHostInfo('127.0.0.1').attrs)

  def testGetVersionFromDir(self):
    au = self._DummyAutoupdateConstructor()

    # New-style version number.
    self.assertEqual(
        au._GetVersionFromDir('/foo/x86-alex/R16-1102.0.2011_09_30_0806-a1'),
        '1102.0.2011_09_30_0806')

    # Old-style version number.
    self.assertEqual(
        au._GetVersionFromDir('/foo/x86-alex/0.15.938.2011_08_23_0941-a1'),
        '0.15.938.2011_08_23_0941')

  def testCanUpdate(self):
    au = self._DummyAutoupdateConstructor()

    # When both the client and the server have new-style versions, we should
    # just compare the tokens directly.
    self.assertTrue(
        au._CanUpdate('1098.0.2011_09_28_1635', '1098.0.2011_09_30_0806'))
    self.assertTrue(
        au._CanUpdate('1098.0.2011_09_28_1635', '1100.0.2011_09_26_0000'))
    self.assertFalse(
        au._CanUpdate('1098.0.2011_09_28_1635', '1098.0.2011_09_26_0000'))
    self.assertFalse(
        au._CanUpdate('1098.0.2011_09_28_1635', '1096.0.2011_09_30_0000'))

    # When the device has an old four-token version number, we should skip the
    # first two tokens and compare the rest.  If there's a tie, go with the
    # server's version.
    self.assertTrue(au._CanUpdate('0.16.892.0', '892.0.1'))
    self.assertTrue(au._CanUpdate('0.16.892.0', '892.0.0'))
    self.assertFalse(au._CanUpdate('0.16.892.0', '890.0.0'))

    # Test the case where both the client and the server have old-style
    # versions.
    self.assertTrue(au._CanUpdate('0.16.892.0', '0.16.892.1'))
    self.assertFalse(au._CanUpdate('0.16.892.0', '0.16.892.0'))


if __name__ == '__main__':
  unittest.main()
