#!/usr/bin/python2

# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for apache_log_metrics.py"""

from __future__ import print_function

import StringIO
import tempfile
import threading
import time
import unittest

import tail_until_writer_finished


class TestTailUntilWriterFinished(unittest.TestCase):
  """Tests tail_until_writer_finished."""

  def testTail(self):
    self.GetsEntireInput(seek_to_end=True)

  def testRead(self):
    self.GetsEntireInput(seek_to_end=False)

  def GetsEntireInput(self, seek_to_end):
    """Tails a temp file in a thread

    Check that it read the file correctly.
    """

    f = tempfile.NamedTemporaryFile()
    output = StringIO.StringIO()

    f.write('This line will not get read if we seek to end.\n')
    f.flush()

    def Tail():
      tail_until_writer_finished.TailFile(f.name, 0.1, 64000, outfile=output,
                                          seek_to_end=seek_to_end)

    thread = threading.Thread(target=Tail)
    thread.start()

    time.sleep(0.1)  # The inotify process must start before we close the file.

    for i in range(100):
      f.write(str(i) + '\n')
      f.flush()
    f.close()
    thread.join()

    expected = ''.join([str(i) + '\n' for i in range(100)])
    if not seek_to_end:
      expected = 'This line will not get read if we seek to end.\n' + expected
    self.assertEqual(output.getvalue(), expected)


if __name__ == '__main__':
  unittest.main()
