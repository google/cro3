# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for gs_archive_server."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import base64
import gzip
import httplib
import json
import md5
import os
import StringIO
import unittest
import urllib

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
    self.assertStatus(httplib.OK)
    self.assertHeader('Content-Type', tested_file['mime'])
    self.assertEqual(len(self.body), tested_file['size'])

  def test_download_a_non_existing_file(self):
    """Test downloading non-existing files."""
    self.getPage('/download/chromeos-images-archive/existing/file')
    self.assertStatus(httplib.NOT_FOUND)

  def test_download_against_unauthorized_bucket(self):
    """Test downloading from unauthorized bucket."""
    self.getPage('/download/another_bucket/file')
    self.assertStatus(httplib.UNAUTHORIZED)


class MockedGSArchiveServerTest(unittest.TestCase):
  """Unit test of GsArchiveServer using mock objects."""

  def setUp(self):
    """Setup method."""
    self.server = gs_archive_server.GsArchiveServer('')
    self.list_member_mock = mock.MagicMock()
    self.list_member_mock.return_value.iter_lines.return_value = [
        'foo,,,0,3', 'bar,,,3,10', 'baz,,,13,5', 'foo%2Cbar,,,20,10']

  def test_list_member(self):
    """Test list_member RPC."""
    with mock.patch.object(self.server, '_caching_server') as caching_server:
      rsp = mock.MagicMock()
      caching_server.download.return_value = rsp
      rsp.iter_content.return_value = (_A_TAR_FILE[:100], _A_TAR_FILE[100:])
      csv = list(self.server.list_member('baz.tar'))
      self.assertEqual(len(csv), 1)
      file_info = tarfile_utils.TarMemberInfo._make(
          csv[0].rstrip('\n').split(','))
      self.assertEqual(file_info.filename, 'bar')
      self.assertEqual(file_info.record_start, '0')
      self.assertEqual(file_info.record_size, '1024')
      self.assertEqual(file_info.content_start, '512')
      self.assertEqual(file_info.size, '4')

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
    """Test extracting a file from a TAR archive."""
    with mock.patch.object(self.server, '_caching_server') as cache_server:
      cache_server.list_member = self.list_member_mock
      cache_server.download.return_value.headers = {
          'Content-Range': 'bytes 3-12/*'}

      # Extract an existing file.
      self.server.extract('bar.tar', file='bar')
      cache_server.download.assert_called_with('bar.tar',
                                               headers={'Range': 'bytes=3-12'})

      # Extract an non-exist file. Should return '{}'
      self.assertEqual('{}', self.server.extract('bar.tar', file='footar'))

  def test_extract_two_files_from_tar(self):
    """Test extracting two files from a TAR archive."""
    with mock.patch.object(self.server, '_caching_server') as cache_server:
      cache_server.list_member = self.list_member_mock
      cache_server.download.return_value.headers = {
          'Content-Type': 'multipart/byteranges; boundary=xxx'}
      cache_server.download.return_value.status_code = httplib.PARTIAL_CONTENT
      # pylint: disable=protected-access
      gs_archive_server._MAX_RANGES_PER_REQUEST = 100

      with mock.patch('range_response.JsonStreamer'):
        self.server.extract('bar.tar', file=['bar', 'foo'])

      cache_server.download.assert_called_with(
          'bar.tar', headers={'Range': 'bytes=0-2,3-12'})

  def test_extract_many_files_from_tar(self):
    """Test extracting many files which result in a series of range requests."""
    with mock.patch.object(self.server, '_caching_server') as cache_server:
      cache_server.list_member = self.list_member_mock
      cache_server.download.return_value.headers = {
          'Content-Type': 'multipart/byteranges; boundary=xxx'}
      cache_server.download.return_value.status_code = httplib.PARTIAL_CONTENT

      # pylint: disable=protected-access
      gs_archive_server._MAX_RANGES_PER_REQUEST = 1
      with mock.patch('range_response.JsonStreamer'):
        self.server.extract('bar.tar', file=['bar', 'foo'])

      cache_server.download.assert_any_call(
          'bar.tar', headers={'Range': 'bytes=0-2'})
      cache_server.download.assert_any_call(
          'bar.tar', headers={'Range': 'bytes=3-12'})

  def test_decompress_tgz(self):
    """Test decompress a tgz file."""
    with mock.patch.object(self.server, '_caching_server') as cache_server:
      cache_server.download.return_value.iter_content.return_value = _A_TGZ_FILE
      rsp = self.server.decompress('baz.tgz')
      self.assertEqual(''.join(rsp), _A_TAR_FILE)

  def test_decompress_bz2(self):
    """Test decompress a bz2 file."""
    with mock.patch.object(self.server, '_caching_server') as cache_server:
      cache_server.download.return_value.iter_content.return_value = _A_BZ2_FILE
      rsp = self.server.decompress('baz.tar.bz2')
      self.assertEqual(''.join(rsp), _A_TAR_FILE)

  def test_decompress_xz(self):
    """Test decompress a xz file."""
    with mock.patch.object(self.server, '_caching_server') as cache_server:
      cache_server.download.return_value.iter_content.return_value = _A_XZ_FILE
      rsp = self.server.decompress('baz.tar.xz')
      self.assertEqual(''.join(rsp), _A_TAR_FILE)

  def test_extract_ztar(self):
    """Test extract a file from a compressed tar archive."""
    with mock.patch.object(self.server, '_caching_server') as cache_server:
      cache_server.list_member.return_value.iter_lines.return_value = [
          'foobar,_,_,0,123']
      cache_server.download.return_value.headers = {
          'Content-Range': 'bytes 0-122/*'}
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
    if rsp.status_code >= httplib.INTERNAL_SERVER_ERROR:
      logging.warning(
          'Testing server %s has internal errors. Some tests are skipped!',
          _TESTING_SERVER)
      return False
    return True
  except Exception:
    logging.warning('No testings server detected. Some tests are skipped!')
    return False


@unittest.skipUnless(testing_server_setup(), 'Testing servers not available!')
class GsCacheBackendIntegrationTest(unittest.TestCase):
  """This is a functional blackbox test

  These tests depend on a full setup of the server and proxy server.
  If either of they is not available, all tests in this class are skipped.
  """

  def _get_page(self, url, headers=None, expect_status=httplib.OK):
    headers = headers.copy() if headers else {}
    if not os.environ.get('WITH_CACHE', None):
      headers['x-no-cache'] = '1'  # bypass all caching to test the whole flow

    rsp = requests.get('%s%s' % (_TESTING_SERVER, url), headers=headers,
                       stream=True)
    self.assertEqual(rsp.status_code, expect_status)
    return rsp

  def _verify_md5(self, content, expected_md5, filename=None):
    """Verify the md5 sum of input content equals to expteced value."""
    m = md5.new()
    m.update(content)
    self.assertEqual(m.hexdigest(), expected_md5, msg=filename)

  def test_download_plain_file(self):
    """Test download RPC."""
    tested_file = _TEST_DATA['a_plain_file']
    rsp = self._get_page('/download%(path)s' % tested_file)
    self.assertEqual(rsp.headers['Content-Length'], str(tested_file['size']))

  def test_download_compressed_file(self):
    """Download a compressed file which won't be decompressed."""
    for k in ('a_zip_file', 'a_tgz_file'):
      tested_file = _TEST_DATA[k]
      rsp = self._get_page('/download%(path)s' % tested_file)
      self.assertEqual(rsp.headers['Content-Length'], str(tested_file['size']))
      self.assertEqual(rsp.headers['Content-Type'], tested_file['mime'])
      self._verify_md5(rsp.content, tested_file['md5'])

  def test_list_member(self):
    """Test list member of a tar file."""
    tested_file = _TEST_DATA['a_tar_file']
    rsp = self._get_page('/list_member%(path)s' % tested_file)
    self.assertEqual(rsp.headers['Content-Type'], 'text/csv;charset=utf-8')
    self._verify_md5(rsp.content, tested_file['members_md5'])

  def test_extract_from_tar(self):
    """Test extracting a file from a tar."""
    for k in ('a_file_from_tar',):
      tested_file = _TEST_DATA[k]
      rsp = self._get_page('/extract/%(from)s?file=%(path)s' % tested_file)
      result = json.loads(rsp.content)
      self.assertEqual(len(result), 1)
      self.assertEqual(result.keys()[0], unicode(tested_file['path']))
      self._verify_md5(result.values()[0], tested_file['md5'])

  def test_extract_files_duplicated(self):
    """Test extracting two duplicated files which should just return one."""
    tested_file = _TEST_DATA['a_file_from_tar']
    rsp = self._get_page('/extract/%(from)s?file=%(path)s&file=%(path)s' %
                         tested_file)
    result = json.loads(rsp.content)
    self.assertEqual(len(result), 1)
    self.assertEqual(result.keys()[0], unicode(tested_file['path']))
    self._verify_md5(result.values()[0], tested_file['md5'])

  def test_extract_non_existing_from_tar(self):
    """Test extracting non-existing file from a tar."""
    tested_file = _TEST_DATA['a_file_from_tar']
    # pylint: disable=protected-access
    response = self._get_page('/extract/%(from)s?file=non-existing-file' %
                              tested_file)
    self.assertEqual(response.content, '{}')

  def test_decompress(self):
    """Test decompress RPC."""
    for k in ('a_tgz_file', 'a_bz2_file', 'a_xz_file'):
      tested_file = _TEST_DATA[k]
      rsp = self._get_page('/decompress%(path)s' % tested_file)
      self.assertEqual(rsp.headers['Content-Type'], 'application/x-tar')
      self._verify_md5(rsp.content, tested_file['z_md5'])

  def test_extract_from_compressed_tar(self):
    """Test extracting a file from a compressed tar file."""
    for k in ('a_file_from_tgz', 'a_file_from_xz', 'a_file_from_bz2'):
      tested_file = _TEST_DATA[k]
      rsp = self._get_page('/extract/%(from)s?file=%(path)s' % tested_file)
      result = json.loads(rsp.content)
      self.assertEqual(len(result), 1)
      self.assertEqual(result.keys()[0], unicode(tested_file['path']))
      self._verify_md5(result.values()[0], tested_file['md5'])

  def test_extract_two_files_by_name(self):
    """Test extracting two files from a compressed tar file by their name."""
    tested_data = {
        'from': '%s/stateful.tgz' % _DIR,
        'file': {
            'var_new/cache/edb/vdb_metadata_delta.json':
                'b085190192bb878efa86cbefd5e81979',
            'dev_image_new/autotest/tools/common.py':
                '634ac656b484758491674530ebe9fbc3',
        }
    }
    tested_data['query'] = urllib.urlencode({'file': tested_data['file']},
                                            doseq=True)
    rsp = self._get_page('/extract/%(from)s?%(query)s' % tested_data)
    result = json.loads(rsp.content)
    self.assertListEqual(sorted(tested_data['file']), sorted(result.keys()))
    for filename, file_content in result.items():
      self._verify_md5(file_content, tested_data['file'][filename], filename)

  def test_extract_one_file_by_pattern(self):
    """Extracting one file by pattern will result in JSON format output."""
    tested_data = {
        'from': '%s/control_files.tar' % _DIR,
        'pattern': '*/dummy_Fail/control',
        'path': 'autotest/client/site_tests/dummy_Fail/control',
        'md5': '2cf8eb4e9384ee66ac56abdf9426a591',
    }
    rsp = self._get_page('/extract/%(from)s?file=%(pattern)s' % tested_data)
    result = json.loads(rsp.content)
    self.assertEqual(len(result), 1)
    filename, file_content = result.items()[0]
    self.assertEqual(filename, unicode(tested_data['path']))
    self._verify_md5(file_content, tested_data['md5'], filename)

  def test_extract_files_by_pattern(self):
    """Test extracting files by pattern."""
    tested_data = {
        'from': '%s/control_files.tar' % _DIR,
        'pattern': '*/dummy_Fail/control*',
        'files': {
            'autotest/client/site_tests/dummy_Fail/control':
                '2cf8eb4e9384ee66ac56abdf9426a591',
            'autotest/client/site_tests/dummy_Fail/control.retry_alwaysfail':
                'ce06ffa9635e02e5908123c31d45c1c5',
            'autotest/client/site_tests/dummy_Fail/control.retry_alwaysflake':
                '43ab0c2961b0e4721f905ea52fde64fd',
            'autotest/client/site_tests/dummy_Fail/control.dependency':
                'e967a894016dcd5bdb6d0b0ace4f8465',
        },
    }
    rsp = self._get_page('/extract/%(from)s?file=%(pattern)s' % tested_data)
    result = json.loads(rsp.content)
    self.assertEqual(len(result), len(tested_data['files']))
    for filename, file_content in result.items():
      self._verify_md5(file_content, tested_data['files'][filename], filename)

  def test_extract_non_existing_files_by_pattern(self):
    """Extract non-existing files by pattern results in '{}'."""
    archive = '%s/control_files.tar' % _DIR,
    rsp = self._get_page('/extract/%s?file=non.existing*files' % archive)
    self.assertEqual(rsp.content, '{}')


if __name__ == "__main__":
  unittest.main()
