# -*- coding: utf-8 -*-
# Copyright 2018 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittests for parsing bits in issuetracker."""

from __future__ import print_function
import unittest

import issuetracker


class CleanSTTest(unittest.TestCase):
    """Tests for issuetracker.clean_st."""
    def test_empty(self):
        """Test empty list returns sane values."""
        self.assertEqual([], issuetracker.clean_st([]))

    def test_two_sets(self):
        """Test sanity with more than 1 stacktrace."""
        inp = [
            set([' worker_thread+0x224/0x1900 kernel/workqueue.c:2248']),
            set([' ret_from_fork+0x3a/0x50 arch/x86/entry/entry_64.S:402'])
        ]
        expected = [set(['worker_thread']), set(['ret_from_fork'])]
        self.assertEqual(expected, issuetracker.clean_st(inp))

    def test_not_useful(self):
        """Test sanity with stacktrace data that is not useful."""
        inp = [set([' <IRQ>'])]
        expected = [set([])]
        self.assertEqual(expected, issuetracker.clean_st(inp))

    def test_expected1(self):
        """Test sanity against expected format."""
        inp = [set([' worker_thread+0x224/0x1900 kernel/workqueue.c:2248',
                    ' ret_from_fork+0x3a/0x50 arch/x86/entry/entry_64.S:402',
                    ' kthread+0x359/0x430 kernel/kthread.c:232'])]
        expected = [set(['kthread', 'worker_thread', 'ret_from_fork'])]
        self.assertEqual(expected, issuetracker.clean_st(inp))

    def test_expected2(self):
        """Test sanity against expected format."""
        inp = [set([
            ' [<ffffffff81c635e6>] __blkdev_driver_ioctl block/ioctl.c:288',
            (' [<ffffffff81c635e6>] blkdev_ioctl+0x7a6/0x1a30 '
             'block/ioctl.c:584')
        ])]
        expected = [set(['__blkdev_driver_ioctl', 'blkdev_ioctl'])]
        self.assertEqual(expected, issuetracker.clean_st(inp))

    def test_expected3(self):
        """Test sanity against expected format."""
        inp = [set([
            ' <EOI>  [<ffffffff81210b51>] ? a+0x1a1/0x440 b/c/d.c:3595'
        ])]
        expected = [set(['a'])]
        self.assertEqual(expected, issuetracker.clean_st(inp))


class GetStacktraceTest(unittest.TestCase):
    """Tests for issuetracker.get_stacktrace."""
    def test_empty(self):
        """Test empty list returns sane values."""
        self.assertEqual([], issuetracker.get_stacktrace(0, []))

    def test_expected1(self):
        """Test sanity against expected format."""
        inp = """
> Call Trace:
>  worker_thread+0x224/0x1900 kernel/workqueue.c:2248
>  ret_from_fork+0x3a/0x50 arch/x86/entry/entry_64.S:402
> <random_stuff>
> Call Trace:
>  [<ffffffff81c635e6>] __blkdev_driver_ioctl block/ioctl.c:288 [inline]
>  [<ffffffff81c635e6>] blkdev_ioctl+0x7a6/0x1a30 block/ioctl.c:584
""".splitlines()
        expected = [set(['worker_thread', 'ret_from_fork']),
                    set(['__blkdev_driver_ioctl', 'blkdev_ioctl'])]
        self.assertEqual(expected, issuetracker.get_stacktrace(0, inp))

    def test_expected2(self):
        """Test sanity against expected format."""
        inp = """
> something
> truly
> random
> Call Trace:
>  worker_thread+0x224/0x1900 kernel/workqueue.c:2248
>  ret_from_fork+0x3a/0x50 arch/x86/entry/entry_64.S:402
> <random_stuff>
> Call Trace:
>  [<ffffffff81c635e6>] __blkdev_driver_ioctl block/ioctl.c:288 [inline]
>  [<ffffffff81c635e6>] blkdev_ioctl+0x7a6/0x1a30 block/ioctl.c:584
""".splitlines()
        expected = [set(['worker_thread', 'ret_from_fork']),
                    set(['__blkdev_driver_ioctl', 'blkdev_ioctl'])]
        self.assertEqual(expected, issuetracker.get_stacktrace(3, inp))


if __name__ == '__main__':
    unittest.main()
