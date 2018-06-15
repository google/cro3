# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module provides utils to handle response of "Range Request"."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import itertools
import json
import re

import constants

_RANGE_HEADER_SEPARATORS = re.compile('[-/ ]')

_ContentRangeHeader = collections.namedtuple('_ContentRangeHeader',
                                             ('bytes', 'start', 'end', 'total'))


class FormatError(Exception):
  """Exception raised when we parse wrong format of response."""


class NoFileFoundError(Exception):
  """Exception raised when we cannot get a file match the range."""


class ResponseQueueError(Exception):
  """Exception raised when trying to queue responses not allowed."""


def _get_file_by_range_header(range_header_str, file_name_map):
  """Get file name and size by the Content-Range header.

  The format of Content-Range header is like:
    Content-Range: bytes <start>-<end>/<total>
  We get the <start> and <end> from it and retrieve the file name from
  |file_name_map|.

  Args:
    range_header_str: A string of range header.
    file_name_map: A dict of {(<start:str>, <size:int>): filename, ...}.

  Returns:
    A tuple of (filename, size).

  Raises:
    FormatError: Raised when response content interrupted.
    NoFileFoundError: Raised when we cannot get a file matches the range.
  """
  # Split the part of 'Content-Range:' first if needed.
  if range_header_str.lower().startswith('content-range:'):
    range_header_str = range_header_str.split(': ', 1)[1]

  try:
    range_header = _ContentRangeHeader._make(
        _RANGE_HEADER_SEPARATORS.split(range_header_str)
    )
    size = int(range_header.end) - int(range_header.start) + 1
  except (IndexError, ValueError):
    raise FormatError('Wrong format of content range header: %s' %
                      range_header_str)

  try:
    filename = file_name_map[(range_header.start, size)]
  except KeyError:
    raise NoFileFoundError('Cannot find a file matches the range %s' %
                           range_header_str)

  return filename, size


class JsonStreamer(object):
  """A class to stream the responses for range requests.

  The class accepts responses and format the file content in all of them as a
  JSON stream. The format:
    '{"<filename>": "<content>", "<filename>": "<content>", ...}'
  """

  def __init__(self):
    self._files_iter_list = []
    self._can_add_more_response = True

  def queue_response(self, response, file_info_list):
    """Add a reponse to the queue to be streamed as JSON.

    We can add either:
      1. one and only one response for single-part range requests, or
      2. a series of responses for multi-part range requests.

    Args:
      response: An instance of requests.Response, which may be the response of a
        single range request, or a multi-part range request.
      file_info_list: A list of tarfile_utils.TarMemberInfo. We use it to look
        up file name by content start offset and size.

    Raises:
      FormatError: Raised when response to be queued isn't for a range request.
      ResponseQueueError: Raised when either queuing more than one response for
        single-part range request, or mixed responses for single-part and
        multi-part range request.
    """
    if not self._can_add_more_response:
      raise ResponseQueueError(
          'No more reponses can be added when there was a response for '
          'single-part range request in the queue!')

    file_name_map = {(f.content_start, int(f.size)): f.filename
                     for f in file_info_list}

    # Check if the response is for single range, or multi-part range. For a
    # single range request, the response must have header 'Content-Range'. For a
    # multi-part ranges request, the Content-Type header must be like
    # 'multipart/byteranges; ......'.
    content_range = response.headers.get('Content-Range', None)
    content_type = response.headers.get('Content-Type', '')

    if content_range:
      if self._files_iter_list:
        raise ResponseQueueError(
            'Cannot queue more than one responses for single-part range '
            'request, or mix responses for single-part and multi-part.')
      filename, _ = _get_file_by_range_header(content_range, file_name_map)
      self._files_iter_list = [iter([(filename, response.content)])]
      self._can_add_more_response = False

    elif content_type.startswith('multipart/byteranges;'):
      self._files_iter_list.append(
          iter(_FileIterator(response, file_name_map)))

    else:
      raise FormatError('The response is not for a range request.')

  def stream(self):
    """Yield the series of responses content as a JSON stream.

    Yields:
      A JSON stream in format described above.
    """
    files_iter = itertools.chain(*self._files_iter_list)

    json_encoder = json.JSONEncoder()
    filename, content = next(files_iter)
    yield '{%s: %s' % (json_encoder.encode(filename),
                       json_encoder.encode(content))
    for filename, content in files_iter:
      yield ', %s: %s' % (json_encoder.encode(filename),
                          json_encoder.encode(content))
    yield '}'


class _FileIterator(object):
  """The iterator of files in a response of multi-part range request.

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

  def __init__(self, response, file_name_map):
    """Constructor.

    Args:
      response: An instance of requests.response.
      file_name_map: A dict of {(<start:str>, <size:int>): filename, ...}.
    """
    self._response_iter = response.iter_content(
        constants.READ_BUFFER_SIZE_BYTES)
    self._chunk = None
    self._file_name_map = file_name_map

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
    """
    self._read_empty_line()  # The first line is empty.
    while True:
      self._read_line()  # The second line is the boundary.
      self._read_line()  # The line sub content type.
      sub_range_header = self._read_line()  # The line of sub content range.
      if sub_range_header is None:
        break
      self._read_empty_line()  # Another empty line.

      filename, size = _get_file_by_range_header(sub_range_header,
                                                 self._file_name_map)
      content = self._read_bytes(size)

      self._read_empty_line()  # Every content has a trailing '\r\n'.

      bytes_read = 0 if content is None else len(content)
      if bytes_read != size:
        raise FormatError(
            '%s: Error in reading content (read %d B, expect %d B)' %
            (filename, bytes_read, size)
        )

      yield filename, content
