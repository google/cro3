# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing shared helper methods."""

import subprocess


DO_PULL = False


class CommonException(Exception):
    """Exception raised from common."""


def get_stable_branch(kernel, is_rc=False):
    """Returns stable branch name."""
    branch = kernel[1:]
    remote = f"linux-{branch}.y"
    if is_rc:
        return kernel, remote
    return remote, remote


def get_cros_branch(kernel):
    """Returns chromeos branch name."""
    branch = kernel[1:]
    return f"chromeos-{branch}"


def get_cherry_pick_branch(bug_id, kernel):
    """Returns branch name to cherry-pick on."""
    return f"b{bug_id}-{kernel}"


def checkout_branch(kernel, branch, remote, remote_branch, kernel_path):
    """Checks into appropriate branch and keeps it up to date."""
    do_checkout(kernel, branch, kernel_path)
    if DO_PULL:
        do_pull(kernel, remote, remote_branch, kernel_path)


def do_checkout(kernel, branch, kernel_path):
    """Checks into given branch."""
    try:
        subprocess.check_call(
            ["git", "checkout", branch],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=kernel_path,
        )
    except subprocess.CalledProcessError:
        raise CommonException(f"Checkout failed for {kernel}")


def do_pull(kernel, remote, remote_branch, kernel_path):
    """Pulls from given branch."""
    try:
        subprocess.check_call(
            ["git", "pull", remote, remote_branch],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=kernel_path,
        )
    except subprocess.CalledProcessError:
        raise CommonException(f"Pull failed for {kernel}")


def get_commit_message(kernel_path, sha):
    """Returns commit message."""
    try:
        cmd = ["git", "-C", kernel_path, "log", "--format=%B", "-n", "1", sha]
        commit_message = subprocess.check_output(
            cmd, stderr=subprocess.DEVNULL, encoding="utf-8"
        )

        return commit_message.rstrip() + "\n"
    except subprocess.CalledProcessError:
        raise CommonException(
            f"Could not retrieve commit in {kernel_path} for {sha}"
        )


def get_sha(kernel_path):
    """Returns most recent commit sha."""
    try:
        sha = subprocess.check_output(
            ["git", "log", "-1", "--format=%H"],
            stderr=subprocess.DEVNULL,
            cwd=kernel_path,
            encoding="utf-8",
        )
    except subprocess.CalledProcessError:
        raise Exception("Sha was not found")

    return sha.rstrip("\n")
