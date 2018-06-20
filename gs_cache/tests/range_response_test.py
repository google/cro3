# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests of range_response."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import unittest

import mock

import range_response
import tarfile_utils


# pylint: disable=protected-access
class JsonStreamerBasicTest(unittest.TestCase):
  """Basic test case for range_response.JsonStreamer."""

  def setUp(self):
    self.streamer = range_response.JsonStreamer()
    self.single_part_response = mock.MagicMock()
    self.single_part_response.headers = {'Content-Range': 'bytes 100-1099/*'}
    self.single_part_response.content = 'A' * 1000
    self.file_info_list = [tarfile_utils.TarMemberInfo('foo', '', '', '100',
                                                       '1000')]

  def test_single_part_response(self):
    """Test handling of single-part response."""
    self.streamer.queue_response(self.single_part_response, self.file_info_list)
    result = json.loads(''.join(self.streamer.stream()))
    self.assertDictEqual(result, {'foo': 'A' * 1000})

  def test_add_response_not_for_range_request(self):
    """Test add response which not for range request."""
    response = mock.MagicMock()
    response.headers = {}
    with self.assertRaises(range_response.FormatError):
      self.streamer.queue_response(response, [])

  def test_add_two_single_part_response(self):
    """Test adding two single-part response."""
    self.streamer.queue_response(self.single_part_response, self.file_info_list)
    with self.assertRaises(range_response.ResponseQueueError):
      self.streamer.queue_response(self.single_part_response, [])

  def test_add_single_part_after_a_multi_part(self):
    """Test adding a single-part response after some multi-part responses."""
    response = mock.MagicMock()
    response.headers = {
        'Content-Type': 'multipart/byteranges; boundary=boundary',
    }
    response.iter_content.return_value = iter([''])
    self.streamer.queue_response(response, self.file_info_list)

    with self.assertRaises(range_response.ResponseQueueError):
      self.streamer.queue_response(self.single_part_response, [])


class MultiPartResponseTest(unittest.TestCase):
  """Test class for handling one response of multi-part range request."""

  def setUp(self):
    self.response = mock.MagicMock()
    self.response.headers = {
        'Content-Type': 'multipart/byteranges; boundary=boundary',
    }
    self.file_info_list = [
        tarfile_utils.TarMemberInfo('foo', '', '', '10', '10'),
        tarfile_utils.TarMemberInfo('bar', '', '', '123', '1000')]

    self.streamer = range_response.JsonStreamer()

    self.good_response = [
        '\r\nboundary\r\nContent-Type: some/type\r',
        '\nContent-Range: bytes 10-19/T\r\n\r\n012',
        '3456789\r\nboundary\r\nContent-Type: some',
        '/type\r\nContent-Range: bytes 123-1122/T\r'
        '\n\r\n' + 'a' * 400,
        'a' * 600,
        '\r\nboundary--\r\n',
    ]

  def test_stream__empty_response(self):
    """Test streaming empty response."""
    self.response.iter_content.return_value = iter([''])
    self.streamer.queue_response(self.response, self.file_info_list)
    with self.assertRaises(range_response.FormatError):
      ''.join(self.streamer.stream())

  def test_stream__multipart_ranges(self):
    """Test streaming files in one response."""
    self.response.iter_content.return_value = iter(self.good_response)
    self.streamer.queue_response(self.response, self.file_info_list)
    result = json.loads(''.join(self.streamer.stream()))
    self.assertDictEqual(result, {'foo': '0123456789', 'bar': 'a' * 1000})

  def test_stream__two_multipart_ranges(self):
    """Test streaming files in two responses."""
    self.response.iter_content.return_value = iter(self.good_response)
    self.streamer.queue_response(self.response, self.file_info_list)

    response2 = mock.MagicMock()
    response2.headers = self.response.headers
    response2.iter_content.return_value = iter(self.good_response)
    self.streamer.queue_response(
        response2,
        [tarfile_utils.TarMemberInfo('FOO', '', '', '10', '10'),
         tarfile_utils.TarMemberInfo('BAR', '', '', '123', '1000')])

    result = json.loads(''.join(self.streamer.stream()))
    self.assertDictEqual(result, {'foo': '0123456789', 'FOO': '0123456789',
                                  'bar': 'a' * 1000, 'BAR': 'a' * 1000})

  def test_stream__file_not_found(self):
    """Test streaming which cannot find file names."""
    self.response.iter_content.return_value = iter([
        '\r\nboundary\r\nContent-Type: some/type\r',
        '\nContent-Range: bytes 10-19/T\r\n\r\n012',
        '3456789\r\n',
        '\r\nboundary--\r\n',
    ])
    self.streamer.queue_response(self.response, [])
    with self.assertRaises(range_response.NoFileFoundError):
      list(self.streamer.stream())

  def test_stream__bad_sub_range_header(self):
    """Test streaming with bad range header."""
    self.response.iter_content.return_value = iter([
        '\r\nboundary\r\nContent-Type: some/type\r',
        '\nContent-RangeXXXXXXXXXXXXXXX'
    ])
    self.streamer.queue_response(self.response, [])
    with self.assertRaises(range_response.FormatError):
      list(self.streamer.stream())

  def test_stream__bad_size(self):
    """Test streaming with bad file size."""
    self.response.iter_content.return_value = iter([
        '\r\nboundary\r\nContent-Type: some/type\r',
        '\nContent-Range: bytes 10-19/T\r\n\r\n012',
        '34\r\n',
        '\r\nboundary--\r\n',
    ])
    self.streamer.queue_response(self.response, self.file_info_list)
    with self.assertRaises(range_response.FormatError):
      list(self.streamer.stream())

  def test_stream__single_range(self):
    """Test formatting a single range response."""
    self.response.headers = {'Content-Type': 'some/type',
                             'Content-Range': 'bytes 10-19/*'}
    self.response.content = 'x' * 10
    self.streamer.queue_response(self.response, self.file_info_list)
    result = ''.join(self.streamer.stream())
    self.assertEqual(result, json.dumps({'foo': self.response.content}))
