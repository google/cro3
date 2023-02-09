#!/usr/bin/env python3
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Disable pylint noise
# pylint: disable=import-error

"""Integration tests"""

from os import path

from githelpers import branch_name
from githelpers import checkout
from rebase_config import baseline_repo
from rebase_config import rebase_repo
import sh

from config import rebase_target
from config import topiclist


def test_impl(branch_prefix, include_merged, version):
    """Compares topic branches to validate rebase.py

    The test compares each topic branch, as defined in config.py,
    in the rebase_config.rebase_repo against rebase_config.baseline_repo.
    The test doesn't fail eagery, and shows a summary at the end. If
    the difference between the two repositories is large, it is truncated
    to 20 lines. The entire result is always stored in log/test/.
    """

    log_path = f"log/test/{version}"
    sh.mkdir("-p", log_path)

    topics = [topic_entry[0] for topic_entry in topiclist]
    branches = [branch_name(branch_prefix, version, topic) for topic in topics]
    if include_merged:
        branches.append(branch_name(branch_prefix, version, None))
    failures = []

    for branch in branches:
        print(f"Testing branch {branch}...")
        try:
            checkout(rebase_repo, branch)
        except sh.ErrorReturnCode_1:
            print(f"Checkout to {branch} failed on {rebase_repo}.")
            print(f"Aborting testing of {branch_prefix}- branches")
            return
        print("Checkout to", branch, "on", rebase_repo, "ok.")

        try:
            checkout(baseline_repo, branch)
        except sh.ErrorReturnCode_1:
            print(f"Checkout to {branch} failed on {baseline_repo}.")
            print(f"Aborting testing of {branch_prefix}- branches")
            return
        print(f"Checkout to {branch} on {baseline_repo} ok.")

        print("Comparing branches...")
        try:
            # -q: only report differing files
            # -r: recursive
            # --exclude=".git": skip git-specific files
            sh.diff("-qr", "--exclude=.git", rebase_repo, baseline_repo)
        except sh.ErrorReturnCode_1 as e:
            output = e.stdout.decode("utf-8")
            lines = output.splitlines()
            print("Differing results!")
            print("Diff output:")
            if len(lines) > 40:
                for line in lines[:10]:
                    print(line)
                print("[[ -- CUT FOR BREVITY -- ]]")
                for line in lines[-10:]:
                    print(line)
            else:
                print(output, end="")
            log_file = f"{log_path}/{branch}.txt"
            failures.append({"branch": branch, "log": log_file})
            with open(log_file, "w") as f:
                f.write(output)
            print(f"Result saved in {log_file}")

    print("\n===== TEST SUMMARY =====")
    passed_num = len(branches) - len(failures)
    total_num = len(branches)
    print(f"{passed_num}/{total_num} passed")
    if len(failures) != 0:
        print("Failing branches:")
        for failure in failures:
            print(failure["branch"], "->", failure["log"])


def test(branch_prefix, include_merged, version=rebase_target):
    """Ensures invariants for test_impl"""

    if not path.isdir(rebase_repo):
        print(f"No {rebase_repo} directory, perform the setup first.")
        return
    if not path.isdir(baseline_repo):
        print(f"No test baseline kernel directory ({baseline_repo})")
        print(f"Please fetch the known good rebase result for {version}")
        return
    test_impl(branch_prefix, include_merged, version)


if __name__ == "__main__":
    test("triage", False)
    test("kernelupstream", True)
