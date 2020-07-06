# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing shared helper methods."""

import subprocess


class CommonException(Exception):
    """Exception raised from common."""


def get_stable_branch(kernel):
    """Returns stable branch name."""
    branch = kernel[1:]
    return f'linux-{branch}.y'


def get_cros_branch(kernel):
    """Returns chromeos branch name."""
    branch = kernel[1:]
    return f'chromeos-{branch}'


def get_cherry_pick_branch(bug_id, kernel):
    """Returns branch name to cherry-pick on."""
    return f'b{bug_id}-{kernel}'


def checkout_branch(kernel, branch, remote, remote_branch, kernel_path):
    """Checks into appropriate branch and keeps it up to date."""
    do_checkout(kernel, branch, kernel_path)
    do_pull(kernel, remote, remote_branch, kernel_path)


def do_checkout(kernel, branch, kernel_path):
    """Checks into given branch."""
    try:
        subprocess.check_call(['git', 'checkout', branch], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=kernel_path)
    except subprocess.CalledProcessError:
        raise CommonException('Checkout failed for %s' % kernel)


def do_pull(kernel, remote, remote_branch, kernel_path):
    """Pulls from given branch."""
    try:
        subprocess.check_call(['git', 'pull', remote, remote_branch],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              cwd=kernel_path)
    except subprocess.CalledProcessError:
        raise CommonException('Pull failed for %s' % kernel)


def get_commit_message(kernel_path, sha):
    """Returns commit message."""
    try:
        cmd = ['git', '-C', kernel_path, 'log', '--format=%B', '-n', '1', sha]
        commit_message = subprocess.check_output(cmd, stderr=subprocess.DEVNULL,
                                                 encoding='utf-8')

        return commit_message.rstrip() +'\n'
    except subprocess.CalledProcessError:
        raise CommonException('Could not retrieve commit in kernal path %s for sha %s'
                                    % (kernel_path, sha))
