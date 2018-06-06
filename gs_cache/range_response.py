# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module provides utils to handle response of "Range Request"."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import constants


class FormatError(Exception):
  """Exception raised when we parse wrong format of response."""


class NoFileFoundError(Exception):
  """Exception raised when we cannot get a file match the range."""


class FileIterator(object):
  """The iterator of files in a response of multipart range request.

  An example response is like:

    HTTP/1.1 206 Partial Content
    Content-Type: multipart/byteranges; boundary=magic_string
    Content-Length: 282

    --magic_string
    Content-Type: text/html
    Content-Range: bytes 0-50/1270

    <data>
    --magic_string
    Content-Type: text/html
    Content-Range: bytes 100-150/1270

    <data>
    --magic_string--

  In our application, each part is the content of a file. This class iterates
  the files.
  """

  def __init__(self, response, file_info_list):
    """Constructor.

    Args:
      response: An instance of requests.response.
      file_info_list: A list of tarfile_utils.TarMemberInfo. We use it to look
        up file name by content start offset and size.
    """
    self._response_iter = response.iter_content(
        constants.READ_BUFFER_SIZE_BYTES)
    self._chunk = None
    self._file_name_map = {(f.content_start, int(f.size)): f.filename
                           for f in file_info_list}

  def __iter__(self):
    self._chunk = next(self._response_iter)
    return self._iter_files()

  def _read_next_chunk(self):
    """Helper function to read next chunk of data and return current chunk."""
    buffered = self._chunk
    try:
      self._chunk = next(self._response_iter)
    except StopIteration:
      self._chunk = None

    return buffered

  def _read_line(self):
    """Read one CRLF ended line from the response.

    Returns:
      The line read. Return None if nothing to read.
    """
    if self._chunk is None:
      return None

    buffered = ''
    while True:
      buffered += self._chunk
      parts = buffered.split('\r\n', 1)
      if len(parts) == 2:
        line, self._chunk = parts
        return line
      else:  # No '\r\n' in current chunk. Read one more.
        self._read_next_chunk()
        if self._chunk is None:
          return buffered

  def _read_bytes(self, max_bytes):
    """Read at most |max_bytes| bytes from the response.

    Args:
      max_bytes: An integer of maximum bytes of bytes to read.

    Returns:
      The bytes read. Return None if nothing to read.
    """
    if self._chunk is None:
      return None

    buffered = ''
    bytes_remaining = max_bytes
    while True:
      bytes_remaining -= len(self._chunk)
      if bytes_remaining < 0:
        buffered += self._chunk[:bytes_remaining]
        self._chunk = self._chunk[bytes_remaining:]
        return buffered

      buffered += self._read_next_chunk()
      if self._chunk is None:
        return buffered

  def _read_empty_line(self):
    """Read one line and assert it is empty."""
    line = self._read_line()
    if line is None:
      raise FormatError('Expect an empty line, but got EOF.')

    if line:
      raise FormatError('Expect an empty line, but got "%s".' % line)

  def _iter_files(self):
    """Iterate the files in the response.

    Yields:
      A pair of (name, content) of the file.

    Raises:
      FormatError: Raised when response content interrupted.
      NoFileFoundError: Raised when we cannot get a file matches the range.
    """
    self._read_empty_line()  # The first line is empty.
    while True:
      self._read_line()  # The second line is the boundary.
      self._read_line()  # The line sub content type.
      sub_range_header = self._read_line()  # The line of sub content range.
      if sub_range_header is None:
        break
      self._read_empty_line()  # Another empty line.

      # The header format is: "Content-Range: bytes START-END/TOTAL"
      try:
        start, end = sub_range_header.split(' ')[2].split('/')[0].split('-')
        size = int(end) - int(start) + 1
      except (IndexError, ValueError):
        raise FormatError('Wrong format of sub content range header: %s' %
                          sub_range_header)
      try:
        filename = self._file_name_map[(start, size)]
      except KeyError:
        raise NoFileFoundError('Cannot find a file matches the range %s' %
                               sub_range_header)

      content = self._read_bytes(size)
      self._read_empty_line()  # Every content has a trailing '\r\n'.

      bytes_read = 0 if content is None else len(content)
      if bytes_read != size:
        raise FormatError(
            '%s: Error in reading content (read %d B, expect %d B)' %
            (filename, bytes_read, size)
        )

      yield filename, content
