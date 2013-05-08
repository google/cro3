#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Block diff utility."""

import optparse
import sys


class BlockDiffError(Exception):
  pass


def BlockDiff(block_size, file1, file2, name1, name2, max_length=-1):
  """Performs a binary diff of two files by blocks.

  Args:
    block_size: the size of a block to diff by
    file1: first file object
    file2: second file object
    name1: name of first file (for error reporting)
    name2: name of second file (for error reporting)
    max_length: the maximum length to read/diff in bytes (optional)
  Returns:
    A list of (start, length) pairs representing block extents that differ
    between the two files.
  Raises:
    BlockDiffError if there were errors while diffing.

  """
  if max_length < 0:
    max_length = sys.maxint
  diff_list = []
  num_blocks = extent_start = extent_length = 0
  while max_length or extent_length:
    read_length = min(max_length, block_size)
    data1 = file1.read(read_length)
    data2 = file2.read(read_length)
    if len(data1) != len(data2):
      raise BlockDiffError('read %d bytes from %s but %d bytes from %s' %
                           (len(data1), name1, len(data2), name2))

    if data1 != data2:
      # Data is different, mark it down.
      if extent_length:
        # Stretch the current diff extent.
        extent_length += 1
      else:
        # Start a new diff extent.
        extent_start = num_blocks
        extent_length = 1
    elif extent_length:
      # Record the previous extent.
      diff_list.append((extent_start, extent_length))
      extent_length = 0

    # Are we done reading?
    if not data1:
      break

    max_length -= len(data1)
    num_blocks += 1

  return diff_list


def main(argv):
  # Parse command-line arguments.
  parser = optparse.OptionParser(
      usage='Usage: %prog FILE1 FILE2',
      description='Compare FILE1 and FILE2 by blocks.')

  parser.add_option('-b', '--block-size', metavar='NUM', type=int, default=4096,
                    help='the block size to use (default: %default)')
  parser.add_option('-m', '--max-length', metavar='NUM', type=int, default=-1,
                    help='maximum number of bytes to compared')

  opts, args = parser.parse_args(argv[1:])

  try:
    name1, name2 = args
  except ValueError:
    parser.error('unexpected number of arguments')

  # Perform the block diff.
  try:
    with open(name1) as file1:
      with open(name2) as file2:
        diff_list = BlockDiff(opts.block_size, file1, file2, name1, name2,
                              opts.max_length)
  except BlockDiffError as e:
    print >> sys.stderr, 'Error:', e
    return 2

  # Print the diff, if such was found.
  if diff_list:
    total_diff_blocks = 0
    for extent_start, extent_length in diff_list:
      total_diff_blocks += extent_length
      print('%d->%d (%d)' %
            (extent_start, extent_start + extent_length, extent_length))

    print 'total diff: %d blocks' % total_diff_blocks
    return 1

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
