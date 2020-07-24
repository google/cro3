# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for patching cherry-picked commit from LINUX kernel to Chromium OS kernel."""

import subprocess
import sys
import os
import logging
import re

from cvelib import common, logutils


LOGGER = logutils.setuplogging(loglvl=logging.DEBUG, name='PatchApplier')


class PatchApplierException(Exception):
    """Exception raised from patchapplier."""


def create_commit_message(kernel_path, sha, bug_id):
    """Generates new commit message."""
    bug_test_line = f'BUG=chromium:{bug_id}\nTEST=CQ\n\n'

    org_msg = common.get_commit_message(kernel_path, sha)

    cherry_picked = f'(cherry picked from commit {sha})\n\n'

    return f'UPSTREAM: {org_msg}{cherry_picked}{bug_test_line}'


def fetch_linux_kernel(kernel_path):
    """Fetch LINUX repo in CHROMIUMOS_KERNEL."""
    if os.getenv('LINUX') == '':
        raise PatchApplierException('Environment variable LINUX is not set')

    try:
        subprocess.check_call(['git', 'fetch', os.getenv('LINUX'), 'master'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              cwd=kernel_path)
        return os.getenv('LINUX')
    except subprocess.CalledProcessError as e:
        raise PatchApplierException(e)
    except FileNotFoundError:
        raise PatchApplierException('Kernel is non-existent')


def create_new_cherry_pick_branch(kernel, bug_id, kernel_path):
    """Creates and checks into new branch for cherry-picking."""
    branch = common.get_cherry_pick_branch(bug_id, kernel)

    try:
        subprocess.check_output(['git', 'checkout', '-b', branch], stderr=subprocess.PIPE,
                                cwd=kernel_path)
    except subprocess.CalledProcessError as e:
        # Checkouts to branch if it exists already.
        if 'already exists' in e.stderr.decode(sys.getfilesystemencoding()):
            common.do_checkout(kernel, branch, kernel_path)
        else:
            raise PatchApplierException(f'Creating branch {branch} failed')


def cherry_pick(kernel_path, sha, bug_id):
    """Cherry-picking commit into kernel."""
    fix_commit_message = create_commit_message(kernel_path, sha, bug_id)

    try:
        subprocess.check_output(['git', 'cherry-pick', '-s', sha],
                                stderr=subprocess.PIPE, cwd=kernel_path)
    except subprocess.CalledProcessError as e:
        if 'bad revision' in e.stderr.decode(sys.getfilesystemencoding()):
            raise PatchApplierException(f'Invalid sha: {sha}')
        subprocess.check_call(['git', 'cherry-pick', '--abort'], cwd=kernel_path)
        return False

    subprocess.check_call(['git', 'commit', '--amend', '-s', '-m', fix_commit_message],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          cwd=kernel_path)
    return True


def modify_change_id(msg, kernel, kernel_path, test_change_ids):
    """Modifes change id of commit to point to a test CL."""
    m = re.findall('^Change-Id: (I[a-z0-9]{40})$', msg, re.M)

    if not m:
        LOGGER.error('No change id found.')
        return

    change_id = m[0]
    new_msg = msg.replace(change_id, test_change_ids[kernel])

    try:
        subprocess.check_call(['git', 'commit', '--amend', '-m', new_msg],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              cwd=kernel_path)
    except subprocess.CalledProcessError:
        raise PatchApplierException(f'Failed to modify the change id for {kernel}')


def apply_patch(sha, bug_id, kernel_versions, test_change_ids=None):
    """Applies patch from LINUX to Chromium OS kernel."""
    cp_status = {}

    if os.getenv('CHROMIUMOS_KERNEL') == '':
        raise PatchApplierException('Environment variable CHROMIUMOS_KERNEL is not set')

    for kernel in kernel_versions:
        LOGGER.debug(f'Trying to apply patch {sha} to {kernel}')

        kernel_path = os.path.join(os.getenv('CHROMIUMOS_KERNEL'), kernel)

        fetch_linux_kernel(kernel_path)

        branch = common.get_cros_branch(kernel)
        common.checkout_branch(kernel, f'cros/{branch}', 'cros', branch, kernel_path)

        create_new_cherry_pick_branch(kernel, bug_id, kernel_path)

        cp_status[kernel] = cherry_pick(kernel_path, sha, bug_id)

        # Only not None when triage is in test mode.
        if test_change_ids and cp_status[kernel]:
            new_patch_sha = common.get_sha(kernel_path)
            modify_change_id(common.get_commit_message(kernel_path, new_patch_sha), kernel,
                             kernel_path, test_change_ids)

    return cp_status
