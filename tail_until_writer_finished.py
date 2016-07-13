#!/usr/bin/python2 -u

# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tails a file, and quits when inotify detects that it has been closed."""

from __future__ import print_function

import argparse
import select
import subprocess
import sys
import time
import contextlib


@contextlib.contextmanager
def WriterClosedFile(path):
  """Context manager to watch whether a file is closed by a writer."""
  inotify_process = subprocess.Popen(
      ['inotifywait', '-qe', 'close_write', path],
      stdout=subprocess.PIPE)

  # stdout.read is blocking, so use select.select to detect if input is
  # available.
  def IsClosed():
    read_list, _, _ = select.select([inotify_process.stdout], [], [], 0)
    return bool(read_list)

  try:
    yield IsClosed
  finally:
    inotify_process.kill()


def TailFile(path, sleep_interval, chunk_size,
             outfile=sys.stdout,
             seek_to_end=True):
  """Tails a file, and quits when there are no writers on the file.

  Args:
    path: The path to the file to open
    sleep_interval: The amount to sleep in between reads to reduce wasted IO
    chunk_size: The amount of bytes to read in between print() calls
    outfile: A file handle to write to.  Defaults to sys.stdout
    seek_to_end: Whether to start at the end of the file at |path| when reading.
  """

  def ReadChunks(fh):
    for chunk in iter(lambda: fh.read(chunk_size), b''):
      print(chunk, end='', file=outfile)

  with WriterClosedFile(path) as IsClosed:
    with open(path) as fh:
      if seek_to_end == True:
        fh.seek(0, 2)
      while True:
        ReadChunks(fh)
        if IsClosed():
          # We need to read the chunks again to avoid a race condition where the
          # writer finishes writing some output in between the ReadChunks() and
          # the IsClosed() call.
          ReadChunks(fh)
          break

        # Sleep a bit to limit the number of wasted reads.
        time.sleep(sleep_interval)


def main():
  p = argparse.ArgumentParser(description=__doc__)
  p.add_argument('file', help='The file to tail')
  p.add_argument('--sleep_interval', type=float, default=0.1,
                 help='Time sleeping between file reads')
  p.add_argument('--chunk_size', type=int, default=64 * 2**10,
                 help='Bytes to read before yielding')
  p.add_argument('--from_beginning', action='store_true',
                 help='If given, read from the beginning of the file.')
  args = p.parse_args()

  TailFile(args.file, args.sleep_interval, args.chunk_size,
           seek_to_end=not args.from_beginning)


if __name__ == '__main__':
  main()
