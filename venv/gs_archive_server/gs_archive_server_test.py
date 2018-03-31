# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""Tests for gs_archive_server."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest

import cherrypy
from cherrypy.test import helper

from chromite.lib import gs
from gs_archive_server import gs_archive_server

_DIR = '/gs_archive_server_test'
# some REAL files and info on Google Storage
_TEST_DATA = {
    'a_plain_file': {
        'path': '%s/README.md' % _DIR,
        'mime': 'application/octet-stream',
        'size': 139
    },
}


def access_to_gs():
  """Skip some tests if we cannot access google storage."""
  return gs.GSContext()._TestGSLs()  # pylint:disable=protected-access


@unittest.skipUnless(access_to_gs(), 'Have no access to google storage')
class UnmockedGSArchiveServerTest(helper.CPWebCase):
  """Some integration tests using cherrypy test framework."""
  @staticmethod
  def setup_server():
    """An API used by cherrypy to setup test environment."""
    cherrypy.tree.mount(gs_archive_server.GSArchiveServer())

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


if __name__ == "__main__":
  unittest.main()
