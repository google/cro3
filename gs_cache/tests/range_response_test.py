# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests of range_response."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import unittest

import mock

import range_response
import tarfile_utils


# pylint: disable=protected-access
class FileIteratorTest(unittest.TestCase):
  """Test class for FileIterator."""

  def setUp(self):
    self.response = mock.MagicMock()
    self.file_info_list = [
        tarfile_utils.TarMemberInfo('foo', '', '', '10', '10'),
        tarfile_utils.TarMemberInfo('bar', '', '', '123', '1000')]

  def test_iter_files_empty_response(self):
    self.response.iter_content.return_value = iter([''])
    files = list(range_response.FileIterator(self.response, mock.MagicMock()))
    self.assertListEqual(files, [])

  def test_iter_files(self):
    """Test iterating files in the response."""
    self.response.iter_content.return_value = iter([
        '\r\nboundary\r\nContent-Type: some/type\r',
        '\nContent-Range: bytes 10-19/T\r\n\r\n012',
        '3456789\r\nboundary\r\nContent-Type: some',
        '/type\r\nContent-Range: bytes 123-1122/T\r'
        '\n\r\n' + 'a' * 400,
        'a' * 600,
        '\r\nboundary--\r\n',
    ])

    files = list(range_response.FileIterator(self.response,
                                             self.file_info_list))
    self.assertListEqual(files, [('foo', '0123456789'), ('bar', 'a' * 1000)])

  def test_iter_files_file_not_found(self):
    """Test iter_files which cannot find file names."""
    self.response.iter_content.return_value = iter([
        '\r\nboundary\r\nContent-Type: some/type\r',
        '\nContent-Range: bytes 10-19/T\r\n\r\n012',
        '3456789\r\n',
        '\r\nboundary--\r\n',
    ])
    with self.assertRaises(range_response.NoFileFoundError):
      list(range_response.FileIterator(self.response, []))

  def test_iter_files_bad_range_header(self):
    """Test iter_files with bad range header."""
    self.response.iter_content.return_value = iter([
        '\r\nboundary\r\nContent-Type: some/type\r',
        '\nContent-RangeXXXXXXXXXXXXXXX'
    ])
    with self.assertRaises(range_response.FormatError):
      list(range_response.FileIterator(self.response, []))

  def test_iter_files_bad_size(self):
    """Test iter_files with bad file size."""
    self.response.iter_content.return_value = iter([
        '\r\nboundary\r\nContent-Type: some/type\r',
        '\nContent-Range: bytes 10-19/T\r\n\r\n012',
        '34\r\n',
        '\r\nboundary--\r\n',
    ])
    with self.assertRaises(range_response.FormatError):
      list(range_response.FileIterator(self.response, self.file_info_list))
