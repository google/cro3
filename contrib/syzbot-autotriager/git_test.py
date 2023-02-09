# -*- coding: utf-8 -*-
# Copyright 2018 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unittests for parsing bits in git."""

from __future__ import print_function

import tempfile
import unittest

import git


class GitTest(unittest.TestCase):
    """Tests for git."""

    def setUp(self):
        self.tfile = tempfile.NamedTemporaryFile()

    def tearDown(self):
        self.tfile.close()

    def test_merge_ignored(self):
        """Test that merge commits are ignored."""
        inp = """
commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
Merge: bbbbbbbbbbbb cccccccccccc
Author: Some author <some@author.com>
Date:   Thu Aug 23 12:09:19 2018 -0700

    Merge commit 'aa9f07a3749ae33849d7595485c30b4fc5912a27' into some_branch

    Change-Id: I2805aef1f4bd5f5fcfb45ecadb522803fe024497
""".strip()

        self.tfile.write(inp)
        self.tfile.flush()
        g = git.Gitlog(self.tfile.name, "/tmp/junk")
        self.assertEqual(0, len(g.commits))

    def test_empty(self):
        """Test that empty gitlogs result in 0 GitCommit's."""
        inp = ""
        self.tfile.write(inp)
        self.tfile.flush()
        g = git.Gitlog(self.tfile.name, "/tmp/junk")
        self.assertEqual(0, len(g.commits))

    def test_normal_1(self):
        """Test parsing of a regular git commit."""
        expected_title = "commit title"
        expected_sha = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
        expected_files = """
a/b/c
ddd
""".strip()
        inp = """
commit: %s
Author: Some author <some@author.com>
Date:   Tue Aug 21 08:47:56 2018 -0700

    %s

    Dummy commit body
    Signed-off-by: some author <some@author.com>

%s
""".strip() % (
            expected_sha,
            expected_title,
            expected_files,
        )

        self.tfile.write(inp)
        self.tfile.flush()
        g = git.Gitlog(self.tfile.name, "/tmp/junk")
        self.assertEqual(1, len(g.commits))

        commit = g.commits[0]
        self.assertEqual(expected_sha, commit.commitid)
        self.assertEqual(expected_title, commit.title)
        self.assertEqual(expected_files, commit.files)

    def test_normal_2(self):
        """Test parsing of 3 commits one of which is a merge commit."""
        expected_titles = ["commit title1", "commit title2"]
        expected_files = [
            """
a/b/c
ddd
""".strip(),
            """
r/e/w
asdfasdf
""".strip(),
        ]

        expected_shas = [
            "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
            "cccccccccccccccccccccccccccccccccccccccc",
        ]
        inp = """
commit %s
Author: Some author <some@author.com>
Date:   Tue Aug 21 08:47:56 2018 -0700

    %s

    Dummy commit body
    Signed-off-by: some author <some@author.com>

%s

commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
Merge: bbbbbbbbbbbb cccccccccccc
Author: Some author <some@author.com>
Date:   Thu Aug 23 12:09:19 2018 -0700

    Merge commit 'aa9f07a3749ae33849d7595485c30b4fc5912a27' into some_branch



commit %s
Author: Some author <some@author.com>
Date:   Tue Aug 21 08:47:56 2018 -0700

    %s

    Dummy commit body
    Signed-off-by: some author <some@author.com>

%s
""".strip() % (
            expected_shas[0],
            expected_titles[0],
            expected_files[0],
            expected_shas[1],
            expected_titles[1],
            expected_files[1],
        )

        self.tfile.write(inp)
        self.tfile.flush()
        g = git.Gitlog(self.tfile.name, "/tmp/junk")
        self.assertEqual(2, len(g.commits))

        self.assertEqual(g.commits[0].commitid, expected_shas[0])
        self.assertEqual(g.commits[0].title, expected_titles[0])
        self.assertEqual(g.commits[0].files, expected_files[0])

        self.assertEqual(g.commits[1].commitid, expected_shas[1])
        self.assertEqual(g.commits[1].title, expected_titles[1])
        self.assertEqual(g.commits[1].files, expected_files[1])


if __name__ == "__main__":
    unittest.main()
