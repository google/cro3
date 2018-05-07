# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utils for manipulating tar format archives.

We use tar command to manipulate tar file other than using Python tarfile module
because that module is very slow in the case of large file.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import collections
import re

from chromite.lib import cros_logging as logging

_logger = logging.getLogger(__name__)


def _round_up_to_512(number):
  """Up round the given |number| to smallest multiple of 512.

  Examples:
    >>> for n in (0, 1, 512, 1025):
    ...   _round_up_to_512(n)
    0
    512
    512
    1536

  Args:
    number: Zero or positive integer.

  Returns:
    The smallest multiple of 512.
  """
  return (number + 511) & -512


def _get_command_result_from_tar_tvR(an_output_line):
  """Get an object of _TarListCommandResult from one line of `tar tvR` output.

  Args:
    an_output_line: One line of `tar tvR` output. Trailing '\n' is acceptable.
      The last line of `tar tvR` is acceptable.

  Returns:
    An object of _TarListCommandResult.
  """
  separators = re.compile('[ \t:]+')
  fields_num = len(_TarListCommandResult._fields)
  fields = re.split(separators, an_output_line.rstrip('\n'),
                    maxsplit=fields_num - 1)
  try:
    return _TarListCommandResult._make(fields)
  except TypeError:
    # The last line of `tar tvR` hasn't enough fields. Fill with fake data.
    _logger.debug('This should be the last line of `tar tvR`: %s',
                  an_output_line)
    fields.extend(_TarListCommandResult._fields[len(fields):])
    return _TarListCommandResult._make(fields)


def _block_to_bytes(block_num):
  """Get offset of the block |block_num| in bytes, i.e. times 512"""
  return block_num << 9  # * 512


# The tuple of tar member information to be returned to caller.
# Fields:
#   filename: The file name of the tar member.
#   record_start: The zero-based start offset of the file record, in bytes.
#   record_size: The size of the file record, in bytes.
#   content_start: The zero-based start offset of the file content, in bytes.
#   size: The size of the file content, in bytes.
TarMemberInfo = collections.namedtuple(
    'TarMemberInfo', ('filename', 'record_start', 'record_size',
                      'content_start', 'size'))


class _TarListCommandResult(collections.namedtuple(
    '_TarListCommandResult', ('block', 'block_num', 'mode', 'ownership',
                              'size_str', 'date', 'hour', 'min', 'filename'))):
  """Information of each member in a Tar archive.

  This class using the output of command `tar tvR` to compute more information
  we need, e.g. file content start offset, etc.

  The output of `tar tvR` is like:
  block 0: -rw-r--r-- user/group <size> <date> <time> <file name>
  ...
  block 7: ** Block of NULs **
  """

  @property
  def record_start(self):
    """Start offset of the file record, in bytes."""
    return _block_to_bytes(int(self.block_num))

  @property
  def size(self):
    return int(self.size_str)


def _get_prev_content_start(cur_record_start, prev_file):
  """Deduct prev file content information from current file record information.

  In tar format, each file record has a header and followed by file content.
  Both header and file content are rounded up to 512 Bytes. The header length is
  variable, but we can get the current file content starting offset by
  subtracting up rounded file size from next file header starting offset, i.e.

  current_offset = block(next_file) * 512 - round_up_to_512(current_size)

  |********|************************.......|********|****
  | header |         content               | header |
  |        |<----- prev_size ----->|
  |        |<- prev_size round up to 512 ->|
           ^prev_content_start             ^cur_record_start

  Args:
    cur_record_start: The zero-based start position of current file record, in
        bytes.
    prev_file: An instance of _TarListCommandResult which has size of the
        previous file.

  Returns:
    The zero-based start position of previous file content, in bytes.
  """
  return cur_record_start - _round_up_to_512(prev_file.size)


def list_tar_members(tar_tvR_output):
  """List the members of a tar with information.

  Yield each member of the tar archive with information of record start/size,
  content start/size, etc.

  Args:
    tar_tvR_output: The output of command 'tar tvR'. Option 'R' print out the
        starting block number of the file record.

  Yields:
    A tuple of data described above in the same order.
  """
  prev_file = _get_command_result_from_tar_tvR(tar_tvR_output.readline())

  for line in tar_tvR_output:
    cur_file = _get_command_result_from_tar_tvR(line)

    prev_content_start = _get_prev_content_start(cur_file.record_start,
                                                 prev_file)
    prev_record_size = cur_file.record_start - prev_file.record_start

    yield TarMemberInfo(prev_file.filename,
                        prev_file.record_start, prev_record_size,
                        prev_content_start, prev_file.size)

    prev_file = cur_file
