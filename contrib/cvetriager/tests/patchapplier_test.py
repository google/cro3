# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Testing script for cvelib/patchapplier.py."""

import unittest
from unittest import mock
import tempfile
import subprocess
import os

from cvelib import patchapplier as pa
from cvelib import common


class TestPatchApplier(unittest.TestCase):
    """Test class for cvelib/patchapplier.py."""

    def setUp(self):
        # Backup $LINUX and $CHROMIUMOS_KERNEL.
        self.linux = os.getenv('LINUX')
        self.cros_kernel = os.getenv('CHROMIUMOS_KERNEL')

        # Make temporary directory for $LINUX.
        self.linux_temp = tempfile.mkdtemp()
        os.environ['LINUX'] = self.linux_temp
        subprocess.check_call(['git', 'init'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              cwd=self.linux_temp)

        for i in range(1, 4):
            subprocess.check_call(['touch', str(i)], cwd=self.linux_temp)
            subprocess.check_call(['git', 'add', str(i)], cwd=self.linux_temp)
            subprocess.check_call(['git', 'commit', '-m', str(i)], stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, cwd=self.linux_temp)

        # Create temporary directory for $CHROMIUMOS_KERNEL.
        self.cros_temp = tempfile.mkdtemp()
        os.environ['CHROMIUMOS_KERNEL'] = self.cros_temp
        subprocess.check_call(['git', 'init'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.cros_temp)

        # Creates branch that represents a mock of a kernel version.
        branch = 'v' + os.path.basename(self.linux_temp)

        subprocess.check_call(['git', 'checkout', '-b', branch], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.cros_temp)

        # Create a commit for branch to be recognized in computer.
        subprocess.check_call(['touch', 'file'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.cros_temp)
        subprocess.check_call(['git', 'add', 'file'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.cros_temp)
        subprocess.check_call(['git', 'commit', '-m', 'random'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.cros_temp)

        # Clone LINUX to CHROMIUMOS_KERNEL.
        subprocess.check_call(['git', 'clone', self.linux_temp], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.cros_temp)

        # Add extra commit to LINUX.
        subprocess.check_call(['touch', '4'], cwd=self.linux_temp)
        subprocess.check_call(['git', 'add', '4'], cwd=self.linux_temp)
        subprocess.check_call(['git', 'commit', '-m', '4'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.linux_temp)

    def tearDown(self):
        if self.linux:
            os.environ['LINUX'] = self.linux
        else:
            del os.environ['LINUX']

        if self.cros_kernel:
            os.environ['CHROMIUMOS_KERNEL'] = self.cros_kernel
        else:
            del os.environ['CHROMIUMOS_KERNEL']

        subprocess.check_call(['rm', '-rf', self.linux_temp])
        subprocess.check_call(['rm', '-rf', self.cros_temp])

    @mock.patch('cvelib.common.checkout_branch')
    def test_apply_patch(self, _):
        """Unit test for apply_patch."""
        sha = common.get_sha(self.linux_temp)
        bug_id = '123'
        kernel_versions = [os.path.basename(self.linux_temp)]

        kernels = pa.apply_patch(sha, bug_id, kernel_versions)

        self.assertTrue(kernels[os.path.basename(self.linux_temp)])

    def test_create_commit_message(self):
        """Unit test for create_commit_message."""
        kernel = os.path.basename(self.linux_temp)
        kernel_path = os.path.join(self.cros_temp, kernel)

        sha = common.get_sha(self.linux_temp)
        bug_id = '123'

        pa.fetch_linux_kernel(kernel_path)

        pa.cherry_pick(kernel_path, sha, bug_id)

        # Retrieves new cherry-picked message.
        msg = common.get_commit_message(kernel_path, common.get_sha(kernel_path))

        check = False
        if 'UPSTREAM:' in msg and 'BUG=' in msg and 'TEST=' in msg:
            check = True

        self.assertTrue(check)

    def test_fetch_linux_kernel(self):
        """Unit test for fetch_linux_kernel."""
        kernel = os.path.basename(self.linux_temp)
        kernel_path = os.path.join(self.cros_temp, kernel)

        linux_expected = self.linux_temp

        linux_actual = pa.fetch_linux_kernel(kernel_path)

        # Checks if fetched from the correct repo.
        self.assertEqual(linux_expected, linux_actual)

    def test_cherry_pick(self):
        """Unit test for cherry_pick."""
        kernel = os.path.basename(self.linux_temp)
        kernel_path = os.path.join(self.cros_temp, kernel)

        sha = common.get_sha(self.linux_temp)
        bug_id = '123'

        pa.fetch_linux_kernel(kernel_path)

        check = pa.cherry_pick(kernel_path, sha, bug_id)

        self.assertTrue(check)

    def test_create_new_cherry_pick_branch(self):
        """Unit test for create_new_cherry_pick_branch."""
        kernel = os.path.basename(self.linux_temp)
        bug_id = '123'

        pa.create_new_cherry_pick_branch(kernel, bug_id, self.cros_temp)

        # Outputs the current branch.
        branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                         stderr=subprocess.DEVNULL, cwd=self.cros_temp)

        expected_branch = f'b{bug_id}-{kernel}'

        self.assertEqual(branch.rstrip(), bytes(expected_branch, encoding='utf-8'))

    def test_create_existing_branch(self):
        """Tests that if the branch is existent, it checkouts to it."""
        kernel = os.path.basename(self.linux_temp)
        bug_id = '123'
        branch = common.get_cherry_pick_branch(bug_id, kernel)

        # Create a branch with expected branch name.
        subprocess.check_call(['git', 'branch', branch], cwd=self.cros_temp)

        # Check if branch will still be checked into.
        pa.create_new_cherry_pick_branch(kernel, bug_id, self.cros_temp)

        # Outputs the current branch.
        branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                         stderr=subprocess.DEVNULL, cwd=self.cros_temp)

        expected_branch = f'b{bug_id}-{kernel}'

        self.assertEqual(branch.rstrip(), bytes(expected_branch, encoding='utf-8'))

    @mock.patch('cvelib.common.checkout_branch')
    def test_invalid_sha(self, _):
        """Test for passing of invalid commit sha."""
        sha = '123'
        bug = '123'
        kernel_versions = [os.path.basename(self.linux_temp)]

        self.assertRaises(common.CommonException, pa.apply_patch,
                          sha, bug, kernel_versions)

    def test_invalid_linux_path(self):
        """Test for invalid LINUX directory."""
        linux = self.linux_temp
        os.environ['LINUX'] = '/tmp/tmp'

        kernel = os.path.basename(self.linux_temp)
        kernel_path = os.path.join(self.cros_temp, kernel)

        self.assertRaises(pa.PatchApplierException, pa.fetch_linux_kernel,
                          kernel_path)

        os.environ['LINUX'] = linux

    def test_empty_env_variables(self):
        """Test for empty LINUX or CHROMIUMOS_KERNEL environement variables."""
        linux = self.linux_temp
        chros_kernel = self.cros_temp

        sha = common.get_sha(self.linux_temp)
        bug = '123'
        kernel_versions = [os.path.basename(self.linux_temp)]

        os.environ['LINUX'] = ''

        self.assertRaises(pa.PatchApplierException, pa.apply_patch,
                          sha, bug, kernel_versions)

        os.environ['LINUX'] = linux
        os.environ['CHROMIUMOS_KERNEL'] = ''

        self.assertRaises(pa.PatchApplierException, pa.apply_patch,
                          sha, bug, kernel_versions)

        os.environ['CHROMIUMOS_KERNEL'] = chros_kernel

    def test_invalid_kernel(self):
        """Test for passing of invalid kernel."""
        sha = common.get_sha(self.linux_temp)
        bug = '123'
        kernel_versions = ['not_a_kernel']

        self.assertRaises(pa.PatchApplierException, pa.apply_patch,
                          sha, bug, kernel_versions)
