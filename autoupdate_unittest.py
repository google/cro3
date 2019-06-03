#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for autoupdate.py."""

from __future__ import print_function

import json
import os
import shutil
import socket
import tempfile
import unittest

import cherrypy
import mox

import autoupdate
import autoupdate_lib
import common_util
import devserver_constants as constants
import xbuddy


_TEST_REQUEST = """
<client_test xmlns:o="http://www.google.com/update2/request" updaterversion="%(client)s" protocol="3.0">
  <app version="%(version)s" track="%(track)s" board="%(board)s" />
  <updatecheck />
  <event eventresult="%(event_result)d" eventtype="%(event_type)d" />
</client_test>"""

# Test request with additional fields needed for full Omaha protocol.
_FULL_TEST_REQUEST = """
<client_test xmlns:o="http://www.google.com/update2/request" updaterversion="%(client)s" protocol="3.0">
  <app version="%(version)s" track="%(track)s" board="%(board)s"
    hardware_class="Test Device" />
  <updatecheck />
  <event eventresult="%(event_result)d" eventtype="%(event_type)d" />
</client_test>"""

#pylint: disable=W0212
class AutoupdateTest(mox.MoxTestBase):
  """Tests for the autoupdate.Autoupdate class."""

  def setUp(self):
    mox.MoxTestBase.setUp(self)
    self.mox.StubOutWithMock(common_util, 'GetFileSize')
    self.mox.StubOutWithMock(common_util, 'GetFileSha1')
    self.mox.StubOutWithMock(common_util, 'GetFileSha256')
    self.mox.StubOutWithMock(common_util, 'IsInsideChroot')
    self.mox.StubOutWithMock(autoupdate_lib, 'GetUpdateResponse')
    self.mox.StubOutWithMock(autoupdate.Autoupdate, '_GetRemotePayloadAttrs')
    self.port = 8080
    self.test_board = 'test-board'
    self.build_root = tempfile.mkdtemp('autoupdate_build_root')
    self.latest_dir = '12345_af_12-a1'
    self.latest_verision = '12345_af_12'
    self.static_image_dir = tempfile.mkdtemp('autoupdate_static_dir')
    self.hostname = '%s:%s' % (socket.gethostname(), self.port)
    self.test_dict = {
        'client': 'ChromeOSUpdateEngine-1.0',
        'version': 'ForcedUpdate',
        'track': 'test-channel',
        'board': self.test_board,
        'event_result': 2,
        'event_type': 3
    }
    self.test_data = _TEST_REQUEST % self.test_dict
    self.sha1 = 12345
    self.size = 54321
    self.url = 'http://%s/static/update.gz' % self.hostname
    self.payload = 'My payload'
    self.sha256 = 'SHA LA LA'
    cherrypy.request.base = 'http://%s' % self.hostname
    common_util.MkDirP(self.static_image_dir)
    self._xbuddy = xbuddy.XBuddy(False,
                                 static_dir=self.static_image_dir)
    self.mox.StubOutWithMock(xbuddy.XBuddy, '_GetArtifact')

  def tearDown(self):
    shutil.rmtree(self.build_root)
    shutil.rmtree(self.static_image_dir)

  def _DummyAutoupdateConstructor(self, **kwargs):
    """Creates a dummy autoupdater.  Used to avoid using constructor."""
    dummy = autoupdate.Autoupdate(self._xbuddy,
                                  static_dir=self.static_image_dir,
                                  **kwargs)
    return dummy

  def testGetRightDeltaPayloadDir(self):
    """Test that our directory is what we expect it to be for updates."""
    self.mox.StubOutWithMock(common_util, 'GetFileMd5')
    src_image = 'test_src_image'
    target_image = 'test_target_image'
    src_hash = '12345'
    target_hash = '67890'

    common_util.GetFileMd5(src_image).AndReturn(src_hash)
    common_util.GetFileMd5(target_image).AndReturn(target_hash)

    self.mox.ReplayAll()
    au_mock = self._DummyAutoupdateConstructor()
    update_dir = au_mock.FindCachedUpdateImageSubDir(src_image, target_image)
    self.assertEqual(os.path.basename(update_dir),
                     '%s_%s' % (src_hash, target_hash))
    self.mox.VerifyAll()

  def testGenerateLatestUpdateImage(self):
    """Test default behavior in response to plain update call."""
    latest_label = os.path.join(self.test_board, self.latest_dir)
    # Generate a fake latest image
    latest_image_dir = os.path.join(self.static_image_dir, latest_label)
    common_util.MkDirP(latest_image_dir)
    image = os.path.join(latest_image_dir, constants.TEST_IMAGE_FILE)
    with open(image, 'w') as fh:
      fh.write('')

    self.mox.StubOutWithMock(autoupdate.Autoupdate,
                             'GenerateUpdateImageWithCache')
    au_mock = self._DummyAutoupdateConstructor()

    common_util.IsInsideChroot().AndReturn(True)
    self._xbuddy._GetArtifact(
        [''], board=self.test_board, lookup_only=True, image_dir=None,
        version=None).AndReturn((latest_label, constants.TEST_IMAGE_FILE))

    au_mock.GenerateUpdateImageWithCache(
        os.path.join(self.static_image_dir, self.test_board, self.latest_dir,
                     constants.TEST_IMAGE_FILE)).AndReturn('update.gz')

    self.mox.ReplayAll()
    test_data = _TEST_REQUEST % self.test_dict
    self.assertTrue(au_mock.HandleUpdatePing(test_data))
    self.mox.VerifyAll()

  def testHandleUpdatePingForForcedImage(self):
    """Test update response to having a forced image."""
    self.mox.StubOutWithMock(autoupdate.Autoupdate,
                             'GenerateUpdateImageWithCache')
    self.mox.StubOutWithMock(autoupdate.Autoupdate, '_StoreMetadataToFile')
    au_mock = self._DummyAutoupdateConstructor()
    test_data = _TEST_REQUEST % self.test_dict

    # Generate a fake image
    forced_image_dir = '/tmp/path_to_force/'
    forced_image = forced_image_dir + constants.IMAGE_FILE
    common_util.MkDirP(forced_image_dir)
    with open(forced_image, 'w') as fh:
      fh.write('')

    cache_image_dir = os.path.join(self.static_image_dir, 'cache')

    # Mock out GenerateUpdateImageWithCache to make an update file in cache
    def mock_fn(_image):
      print('mock_fn')
      # No good way to introduce an update file during execution.
      cache_dir = os.path.join(self.static_image_dir, 'cache')
      common_util.MkDirP(cache_dir)
      update_image = os.path.join(cache_dir, constants.UPDATE_FILE)
      with open(update_image, 'w') as fh:
        fh.write('')

    common_util.IsInsideChroot().AndReturn(True)
    au_mock.GenerateUpdateImageWithCache(forced_image).WithSideEffects(
        mock_fn).AndReturn('cache')

    common_util.GetFileSha1(os.path.join(
        cache_image_dir, 'update.gz')).AndReturn(self.sha1)
    common_util.GetFileSha256(os.path.join(
        cache_image_dir, 'update.gz')).AndReturn(self.sha256)
    common_util.GetFileSize(os.path.join(
        cache_image_dir, 'update.gz')).AndReturn(self.size)
    au_mock._StoreMetadataToFile(cache_image_dir,
                                 mox.IsA(autoupdate.UpdateMetadata))
    forced_url = 'http://%s/static/%s/update.gz' % (self.hostname,
                                                    'cache')
    autoupdate_lib.GetUpdateResponse(
        self.sha1, self.sha256, self.size, forced_url, False, 0, None, None,
        u'3.0', '', False).AndReturn(self.payload)

    self.mox.ReplayAll()
    au_mock.forced_image = forced_image
    self.assertEqual(au_mock.HandleUpdatePing(test_data), self.payload)
    self.mox.VerifyAll()

  def testHandleForcePregenerateXBuddy(self):
    """Check pregenerating an xbuddy path.

    A forced image that starts with 'xbuddy:' uses the following path to
    obtain an update.
    """
    self.mox.StubOutWithMock(autoupdate.Autoupdate,
                             'GetUpdateForLabel')
    au_mock = self._DummyAutoupdateConstructor()
    au_mock.forced_image = "xbuddy:b/v/a"

    self._xbuddy._GetArtifact(
        ['b', 'v', 'a'],
        image_dir=None).AndReturn(('label', constants.TEST_IMAGE_FILE))

    au_mock.GetUpdateForLabel(
        autoupdate.FORCED_UPDATE, 'b/v/a').AndReturn('p')
    self.mox.ReplayAll()

    au_mock.PreGenerateUpdate()
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
        au_mock.host_infos.GetHostInfo(test_ip).attrs['forced_update_label'],
        test_label)

  def testHandleUpdatePingWithSetUpdate(self):
    """If update is set, it should use the update found in that directory."""
    self.mox.StubOutWithMock(autoupdate.Autoupdate, '_StoreMetadataToFile')
    au_mock = self._DummyAutoupdateConstructor()

    test_data = _TEST_REQUEST % self.test_dict
    test_label = 'new_update-test/the-new-update'
    new_image_dir = os.path.join(self.static_image_dir, test_label)
    new_url = self.url.replace('update.gz', test_label + '/update.gz')

    # Generate a fake payload.
    common_util.MkDirP(new_image_dir)
    update_gz = os.path.join(new_image_dir, constants.UPDATE_FILE)
    with open(update_gz, 'w') as fh:
      fh.write('')

    common_util.GetFileSha1(os.path.join(
        new_image_dir, 'update.gz')).AndReturn(self.sha1)
    common_util.GetFileSha256(os.path.join(
        new_image_dir, 'update.gz')).AndReturn(self.sha256)
    common_util.GetFileSize(os.path.join(
        new_image_dir, 'update.gz')).AndReturn(self.size)
    au_mock._StoreMetadataToFile(new_image_dir,
                                 mox.IsA(autoupdate.UpdateMetadata))
    autoupdate_lib.GetUpdateResponse(
        self.sha1, self.sha256, self.size, new_url, False, 0, None, None,
        u'3.0', '', False).AndReturn(self.payload)

    self.mox.ReplayAll()
    au_mock.HandleSetUpdatePing('127.0.0.1', test_label)
    self.assertEqual(
        au_mock.host_infos.GetHostInfo('127.0.0.1').
        attrs['forced_update_label'],
        test_label)
    self.assertEqual(au_mock.HandleUpdatePing(test_data), self.payload)
    self.assertFalse(
        'forced_update_label' in
        au_mock.host_infos.GetHostInfo('127.0.0.1').attrs)

  def testGetVersionFromDir(self):
    au = self._DummyAutoupdateConstructor()

    # New-style version number.
    self.assertEqual(
        au._GetVersionFromDir('/foo/x86-alex/R16-1102.0.2011_09_30_0806-a1'),
        '1102.0.2011_09_30_0806')

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

  def testHandleUpdatePingRemotePayload(self):
    remote_urlbase = 'http://remotehost:6666'
    remote_payload_path = 'static/path/to/update.gz'
    remote_url = '/'.join([remote_urlbase, remote_payload_path, 'update.gz'])
    au_mock = self._DummyAutoupdateConstructor(urlbase=remote_urlbase,
                                               payload_path=remote_payload_path,
                                               remote_payload=True)

    incomplete_test_data = _TEST_REQUEST % self.test_dict
    complete_test_data = _FULL_TEST_REQUEST % self.test_dict

    au_mock._GetRemotePayloadAttrs(remote_url).AndReturn(
        autoupdate.UpdateMetadata(self.sha1, self.sha256, self.size, False,
                                  0, ''))
    autoupdate_lib.GetUpdateResponse(
        self.sha1, self.sha256, self.size, remote_url, False, 0, None, None,
        u'3.0', '', False).AndReturn(self.payload)

    self.mox.ReplayAll()
    # This should fail because of missing fields.
    self.assertRaises(common_util.DevServerHTTPError,
                      au_mock.HandleUpdatePing, incomplete_test_data)
    # This should have enough information.
    self.assertEqual(au_mock.HandleUpdatePing(complete_test_data), self.payload)
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
