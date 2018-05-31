# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for gs_archive_server."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import base64
import gzip
import md5
import os
import StringIO
import unittest

import cherrypy
import mock
import pytest
import requests
from cherrypy.test import helper

import gs_archive_server
import tarfile_utils
from chromite.lib import cros_logging as logging

_TESTING_SERVER = 'http://127.0.0.1:8888'
_DIR = '/gs_archive_server_test'
# Some REAL files and info on Google Storage.
_TEST_DATA = {
    'a_plain_file': {
        'path': '%s/README.md' % _DIR,
        'mime': 'application/octet-stream',
        'size': 139,
    },
    'a_tar_file': {
        'path': '%s/control_files.tar' % _DIR,
        'members_md5': 'e7fda7e72173f764c54e244673387623',
    },
    'a_file_from_tar': {
        'path': 'autotest/frontend/afe/control_file.py',
        'from': '%s/control_files.tar' % _DIR,
        'md5': '31c71c463eb44aaae37e3f2c92423291',
    },
    'a_zip_file': {
        'path': '%s/au-generator.zip' % _DIR,
        'mime': 'application/zip',
        'size': 6431255,
        'md5': 'd13af876bf8e383f39729a97c4e68f5d'
    },
    # TODO(guocb): find a smaller tgz file for testing
    'a_tgz_file': {
        'path': '%s/stateful.tgz' % _DIR,
        'mime': 'application/gzip',
        'size': 422480062,
        'md5': '4d264876b52b35302f724a227d232165',
        'z_size': 1231759360,
        'z_md5': 'ffdea48f11866130df0e774dccb6684b',
    },
    'a_bz2_file': {
        'path': '%s/paygen_au_canary_control.tar.bz2' % _DIR,
        'z_size': 40960,
        'z_md5': '8b3654f7b056f016182888ccfff7bf33',
    },
    'a_xz_file': {
        'path': '%s/image_scripts.tar.xz' % _DIR,
        'z_size': 51200,
        'z_md5': 'baa91444d9a1d8e173c42dfa776b1b98',
    },
    'a_file_from_tgz': {
        'path': 'dev_image_new/autotest/tools/common.py',
        'from': '%s/stateful.tgz' % _DIR,
        'md5': '634ac656b484758491674530ebe9fbc3'
    },
    'a_file_from_bz2': {
        'path':
            'autotest/au_control_files/control.paygen_au_canary_full_10500.0.0',
        'from': '%s/paygen_au_canary_control.tar.bz2' % _DIR,
        'md5': '5491d80aa4788084d974bd92df67815d'
    },
    'a_file_from_xz': {
        'path': 'mount_image.sh',
        'from': '%s/image_scripts.tar.xz' % _DIR,
        'md5': 'e89dd3eb2fa386c3b0eef538a5ab57c3',
    },
}

# a tgz file with only one file "bar" which content is "foo\n"
_A_TGZ_FILE = base64.b64decode(
    'H4sIAC8VyFoAA+3OMQ7CMAxGYc+cIkdw3DQ9T4pExYBSuc3A7WlhR2JoWd43+vfwxuJyNN3klC'
    'R2McWcRK0feuve9499s2yqQ9r3aKZZgh5etmnLWjwEmVq9jl/+Zr8/ij8nr20+o+skt1ov/24A'
    'AAAAAAAAAAAAAAAAAPzuBWP9bg8AKAAA'
)
_A_TAR_FILE = gzip.GzipFile(fileobj=StringIO.StringIO(_A_TGZ_FILE)).read()

_A_BZ2_FILE = base64.b64decode(
    'QlpoOTFBWSZTWUshPJoAAHb7hMEQAIFAAH+AAAJ5ot4gAIAACCAAdBqDJPSAZAGJ6gkpogANAG'
    'gI/Sqk9CCicBIxvwCiBc5JA0mH1s0BZvi4a8OCJE5TugRAxDV79gdzYHEouEq075mqpvY1sTqW'
    'FfnEr0VMGMYB+LuSKcKEglkJ5NA='
)

_A_XZ_FILE = base64.b64decode(
    '/Td6WFoAAATm1rRGAgAhARYAAAB0L+Wj4Cf/AH5dADEYSqQU1AHJap4MgGYINsXfDuS78Jr4gw'
    'kCk2yRJASEGw9VHGsDGIq8Ciuq0Jk21NnOqMTuhaxViAM0mRq/wjYK0XYkx+tChPKveCLlizo4'
    'PgNcUFEpFWlJWnAiEdRpu0onD3dLX9IE/ehO9ylcdhiyq85LnlQludOjNxW3AAAAAG1LUyfA4L'
    '6gAAGaAYBQAADDUC3DscRn+wIAAAAABFla'
)


@pytest.mark.network
class UnmockedGSArchiveServerTest(helper.CPWebCase):
  """Some integration tests using cherrypy test framework."""
  @staticmethod
  def setup_server():
    """An API used by cherrypy to setup test environment."""
    cherrypy.tree.mount(gs_archive_server.GsArchiveServer(''))

  def test_download_a_file(self):
    """Test normal files downloading."""
    tested_file = _TEST_DATA['a_plain_file']
    self.getPage('/download%(path)s' % tested_file)
    self.assertStatus(200)
    self.assertHeader('Content-Type', tested_file['mime'])
    self.assertEquals(len(self.body), tested_file['size'])

  def test_download_a_non_existing_file(self):
    """Test downloading non-existing files."""
    self.getPage('/download/chromeos-images-archive/existing/file')
    self.assertStatus(404)

  def test_download_against_unauthorized_bucket(self):
    """Test downloading from unauthorized bucket."""
    self.getPage('/download/another_bucket/file')
    self.assertStatus(401)


class MockedGSArchiveServerTest(unittest.TestCase):
  """Unit test of GsArchiveServer using mock objects."""

  def setUp(self):
    """Setup method."""
    self.server = gs_archive_server.GsArchiveServer('')

  def test_list_member(self):
    """Test list_member RPC."""
    with mock.patch.object(self.server, '_caching_server') as caching_server:
      rsp = mock.MagicMock()
      caching_server.download.return_value = rsp
      rsp.iter_content.return_value = (_A_TAR_FILE[:100], _A_TAR_FILE[100:])
      csv = list(self.server.list_member('baz.tar'))
      self.assertEquals(len(csv), 1)
      file_info = tarfile_utils.TarMemberInfo._make(
          csv[0].rstrip('\n').split(','))
      self.assertEquals(file_info.filename, 'bar')
      self.assertEquals(file_info.record_start, '0')
      self.assertEquals(file_info.record_size, '1024')
      self.assertEquals(file_info.content_start, '512')
      self.assertEquals(file_info.size, '4')

      # test char quoting in file name
      with gzip.open(os.path.join(os.path.dirname(__file__),
                                  'index_tar_member_testing.tgz')) as f:
        rsp.iter_content.return_value = f.read()
        members = next(self.server.list_member('baz.tar'))
        for csv in members.rstrip('\n').split('\n'):
          file_info = tarfile_utils.TarMemberInfo._make(csv.split(','))
          # The first element is filename, and all remaining elements are
          # integers.
          _ = [int(d) for d in file_info[1:]]

  def test_extract_from_tar(self):
    """Test extract a file from a TAR archive."""
    with mock.patch.object(self.server, '_caching_server') as cache_server:
      cache_server.list_member.return_value.iter_lines.return_value = [
          'foo,_,_,0,3', 'bar,_,_,3,10', 'baz,_,_,13,5']

      # extract an existing file.
      self.server.extract('bar.tar', file='bar')
      cache_server.download.assert_called_with('bar.tar',
                                               headers={'Range': 'bytes=3-12'})

      # extract an non-exist file.
      with self.assertRaises(cherrypy.HTTPError):
        self.server.extract('bar.tar', file='footar')

  def test_decompress_tgz(self):
    """Test decompress a tgz file."""
    with mock.patch.object(self.server, '_caching_server') as cache_server:
      cache_server.download.return_value.iter_content.return_value = _A_TGZ_FILE
      rsp = self.server.decompress('baz.tgz')
      self.assertEquals(''.join(rsp), _A_TAR_FILE)

  def test_decompress_bz2(self):
    """Test decompress a bz2 file."""
    with mock.patch.object(self.server, '_caching_server') as cache_server:
      cache_server.download.return_value.iter_content.return_value = _A_BZ2_FILE
      rsp = self.server.decompress('baz.tar.bz2')
      self.assertEquals(''.join(rsp), _A_TAR_FILE)

  def test_decompress_xz(self):
    """Test decompress a xz file."""
    with mock.patch.object(self.server, '_caching_server') as cache_server:
      cache_server.download.return_value.iter_content.return_value = _A_XZ_FILE
      rsp = self.server.decompress('baz.tar.xz')
      self.assertEquals(''.join(rsp), _A_TAR_FILE)

  def test_extract_ztar(self):
    """Test extract a file from a compressed tar archive."""
    with mock.patch.object(self.server, '_caching_server') as cache_server:
      cache_server.list_member.return_value.iter_lines.return_value = [
          'foobar,_,_,0,123']
      self.server.extract('baz.tar.gz', file='foobar')
      self.server.extract('baz.tar.bz2', file='foobar')
      self.server.extract('baz.tar.xz', file='foobar')
      self.server.extract('baz.tgz', file='foobar')

      self.assertTrue(cache_server.list_member.called)
      self.assertTrue(cache_server.download.called)


def testing_server_setup():
  """Check if testing server is setup."""
  try:
    rsp = requests.get(_TESTING_SERVER)
    if rsp.status_code >= 500:
      logging.warn(
          'Testing server %s has internal errors. Some tests are skipped!',
          _TESTING_SERVER)
      return False
    return True
  except Exception:
    logging.warn('No testings server detected. Some tests are skipped!')
    return False


@unittest.skipUnless(testing_server_setup(), 'Testing servers not available!')
class GsCacheBackendIntegrationTest(unittest.TestCase):
  """This is a functional blackbox test

  These tests depend on a full setup of the server and proxy server.
  If either of they is not available, all tests in this class are skipped.
  """

  def _get_page(self, url, headers=None, expect_status=200):
    headers = headers.copy() if headers else {}
    if not os.environ.get('WITH_CACHE', None):
      headers['x-no-cache'] = '1'  # bypass all caching to test the whole flow

    rsp = requests.get('%s%s' % (_TESTING_SERVER, url), headers=headers,
                       stream=True)
    self.assertEquals(rsp.status_code, expect_status)
    return rsp

  def _verify_md5(self, content, expected_md5):
    """Verify the md5 sum of input content equals to expteced value."""
    m = md5.new()
    m.update(content)
    self.assertEquals(m.hexdigest(), expected_md5)

  def test_download_plain_file(self):
    """Test download RPC."""
    tested_file = _TEST_DATA['a_plain_file']
    rsp = self._get_page('/download%(path)s' % tested_file)
    self.assertEquals(rsp.headers['Content-Length'], str(tested_file['size']))

  def test_download_compressed_file(self):
    """Download a compressed file which won't be decompressed."""
    for k in ('a_zip_file', 'a_tgz_file'):
      tested_file = _TEST_DATA[k]
      rsp = self._get_page('/download%(path)s' % tested_file)
      self.assertEquals(rsp.headers['Content-Length'], str(tested_file['size']))
      self.assertEquals(rsp.headers['Content-Type'], tested_file['mime'])
      self._verify_md5(rsp.content, tested_file['md5'])

  def test_list_member(self):
    """Test list member of a tar file."""
    tested_file = _TEST_DATA['a_tar_file']
    rsp = self._get_page('/list_member%(path)s' % tested_file)
    self.assertEquals(rsp.headers['Content-Type'], 'text/csv;charset=utf-8')
    self._verify_md5(rsp.content, tested_file['members_md5'])

  def test_extract_from_tar(self):
    """Test extracting a file from a tar."""
    for k in ('a_file_from_tar',):
      tested_file = _TEST_DATA[k]
      rsp = self._get_page('/extract/%(from)s?file=%(path)s' % tested_file)
      self._verify_md5(rsp.content, tested_file['md5'])

  def test_decompress(self):
    """Test decompress RPC."""
    for k in ('a_tgz_file', 'a_bz2_file', 'a_xz_file'):
      tested_file = _TEST_DATA[k]
      rsp = self._get_page('/decompress%(path)s' % tested_file)
      self.assertEquals(rsp.headers['Content-Type'], 'application/x-tar')
      self._verify_md5(rsp.content, tested_file['z_md5'])

  def test_extract_from_compressed_tar(self):
    """Test extracting a file from a compressed tar file."""
    for k in ('a_file_from_tgz', 'a_file_from_xz', 'a_file_from_bz2'):
      tested_file = _TEST_DATA[k]
      rsp = self._get_page('/extract/%(from)s?file=%(path)s' % tested_file)
      self._verify_md5(rsp.content, tested_file['md5'])


if __name__ == "__main__":
  unittest.main()
