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
        'members_md5': '0d5d60e9f10d41c60dd85a7f0081de5d',
    }
}

# a tgz file with only one file "bar" which content is "foo\n"
_A_TGZ_FILE = base64.b64decode(
    'H4sIAC8VyFoAA+3OMQ7CMAxGYc+cIkdw3DQ9T4pExYBSuc3A7WlhR2JoWd43+vfwxuJyNN3klC'
    'R2McWcRK0feuve9499s2yqQ9r3aKZZgh5etmnLWjwEmVq9jl/+Zr8/ij8nr20+o+skt1ov/24A'
    'AAAAAAAAAAAAAAAAAPzuBWP9bg8AKAAA'
)
_A_TAR_FILE = gzip.GzipFile(fileobj=StringIO.StringIO(_A_TGZ_FILE)).read()


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
      (filename, record_start, record_size, record_end,
       content_start, size, content_end) = csv[0].split(',')
      self.assertEquals(filename, 'bar')
      self.assertEquals(record_start, '0')
      self.assertEquals(record_size, '1024')
      self.assertEquals(record_end, '1023')  # 1024 - 1
      self.assertEquals(content_start, '512')
      self.assertEquals(size, '4')
      self.assertEquals(content_end, '515\n')  # 512 + 4 - 1

      # test char quoting in file name
      with gzip.open(os.path.join(os.path.dirname(__file__),
                                  'index_tar_member_testing.tgz')) as f:
        rsp.iter_content.return_value = f.read()
        members = next(self.server.list_member('baz.tar'))
        for csv in members.rstrip('\n').split('\n'):
          # each line can be split into 7 elements, even ',' in filename
          elements = csv.split(',')
          self.assertEquals(len(elements), 7)
          # elements from 1 to 6 are integers
          _ = [int(d) for d in elements[1:7]]


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
class GsCacheBackendFunctionalTest(unittest.TestCase):
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

  def test_list_member(self):
    """Test list member of a tar file."""
    tested_file = _TEST_DATA['a_tar_file']
    rsp = self._get_page('/list_member%(path)s' % tested_file)
    self.assertEquals(rsp.headers['Content-Type'], 'text/csv;charset=utf-8')
    self._verify_md5(rsp.content, tested_file['members_md5'])


if __name__ == "__main__":
  unittest.main()
