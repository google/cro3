# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Unit tests for copybot.py module."""

import json
from unittest import mock

import copybot
import pytest


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


@pytest.mark.parametrize(
    ["exception", "expected"],
    [
        (None, {}),
        (Exception(), {"failure_reason": "FAILURE_UNKNOWN"}),
        (
            copybot.MergeConflictsError(commits=["deadbeef", "deadd00d"]),
            {
                "failure_reason": "FAILURE_MERGE_CONFLICTS",
                "merge_conflicts": [{"hash": "deadbeef"}, {"hash": "deadd00d"}],
            },
        ),
    ],
)
def test_write_json_error(tmp_path, exception, expected):
    err_out = tmp_path / "err.json"
    copybot.write_json_error(err_out, exception)
    assert json.loads(err_out.read_text()) == expected


def test_main_raise_error(tmp_path):
    err_out = tmp_path / "err.json"
    with mock.patch(
        "copybot.run_copybot", side_effect=copybot.PushError("failed to push")
    ):
        with pytest.raises(copybot.PushError):
            copybot.main(
                argv=["--json-out", str(err_out), "upstream", "downstream"]
            )
    assert json.loads(err_out.read_text()) == {
        "failure_reason": "FAILURE_DOWNSTREAM_PUSH_ERROR",
    }
