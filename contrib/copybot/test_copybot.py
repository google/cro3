# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for copybot.py module."""

import copybot


def test_prefix_pseudoheaders():
    """Test the .prefix() method of Pseudoheaders."""
    pseudoheaders = copybot.Pseudoheaders(
        [
            ("Signed-off-by", "Alyssa P. Hacker <aphacker@example.org>"),
            ("CQ-DEPEND", "chromium:1234,chrome-internal:5678"),
        ]
    )

    new_pseudoheaders = pseudoheaders.prefix(keep=["Cq-Depend"])
    commit_message = new_pseudoheaders.add_to_commit_message("Some commit msg")
    assert (
        commit_message
        == """Some commit msg

Original-Signed-off-by: Alyssa P. Hacker <aphacker@example.org>
CQ-DEPEND: chromium:1234,chrome-internal:5678
"""
    )
