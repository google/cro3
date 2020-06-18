# -*-coding: utf-8 -*-

"""Testing script for cvelib/contextgenerator.py."""

import unittest
from unittest import mock
import tempfile
import subprocess
import os

from cvelib import contextgenerator


def create_branch_and_commit_file(path, branch_name, file_name, subject):
    """Creates new branch and commits a new file to it."""
    subprocess.check_call(['git', 'checkout', '-b', branch_name],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                          cwd=path)
    subprocess.check_call(['touch', file_name], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, cwd=path)
    subprocess.check_call(['git', 'add', file_name], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, cwd=path)
    subprocess.check_call(['git', 'commit', '-m', subject], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL, cwd=path)


class TestContextGenerator(unittest.TestCase):
    """Test class for cvelib/contextgenerator.py."""

    # Refers to commit in the linux kernel.
    linux_sha = '54e200ab40fc14c863bcc80a51e20b7906608fce'

    # Subject of linux_sha.
    linux_subject = 'kernel/relay.c: handle alloc_percpu returning NULL in relay_open'

    # Subject of commit given by fixes tag in linux_sha.
    fixes_subject = 'relay: Use per CPU constructs for the relay channel buffer pointers'

    def setUp(self):
        # Backup $CHROMIUMOS_KERNEL, $STABLE, $STABLE_RC.
        self.cros_kernel = os.getenv('CHROMIUMOS_KERNEL')
        self.stable = os.getenv('STABLE')
        self.stable_rc = os.getenv('STABLE_RC')

        # Make temporary directory for $CHROMIUMOS_KERNEL.
        self.cros_temp = tempfile.mkdtemp()
        os.environ['CHROMIUMOS_KERNEL'] = self.cros_temp
        self.kernel_temp1 = os.path.join(self.cros_temp, 'v1.0')
        self.kernel_temp2 = os.path.join(self.cros_temp, 'v2.0')
        os.mkdir(self.kernel_temp1)
        os.mkdir(self.kernel_temp2)
        subprocess.check_call(['git', 'init'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.kernel_temp1)
        subprocess.check_call(['git', 'init'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.kernel_temp2)

        create_branch_and_commit_file(self.kernel_temp1, 'cros/chromeos-1.0', 'new_file',
                                      TestContextGenerator.fixes_subject)

        create_branch_and_commit_file(self.kernel_temp2, 'cros/chromeos-2.0', 'new_file2',
                                      TestContextGenerator.linux_subject)

        # Helps test if commit is in $STABLE.
        self.stable_temp = tempfile.mkdtemp()
        os.environ['STABLE'] = self.stable_temp
        subprocess.check_call(['git', 'init'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.stable_temp)

        create_branch_and_commit_file(self.stable_temp, 'linux-1.0.y', 'file1', 'random subject')

        create_branch_and_commit_file(self.stable_temp, 'linux-2.0.y', 'file2',
                                      TestContextGenerator.linux_subject)

        # Helps test if commit is in $STABLE_RC.
        self.stable_rc_temp = tempfile.mkdtemp()
        os.environ['STABLE_RC'] = self.stable_rc_temp
        subprocess.check_call(['git', 'init'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.stable_rc_temp)

        create_branch_and_commit_file(self.stable_rc_temp, 'linux-1.0.y', 'file', 'random subject')

        create_branch_and_commit_file(self.stable_rc_temp, 'linux-2.0.y', 'file2',
                                      TestContextGenerator.linux_subject)

    def tearDown(self):
        if self.cros_kernel:
            os.environ['CHROMIUMOS_KERNEL'] = self.cros_kernel
        else:
            del os.environ['CHROMIUMOS_KERNEL']

        if self.stable:
            os.environ['STABLE'] = self.stable
        else:
            del os.environ['STABLE']

        if self.stable_rc:
            os.environ['STABLE_RC'] = self.stable_rc
        else:
            del os.environ['STABLE_RC']

        subprocess.check_call(['rm', '-rf', self.cros_temp])
        subprocess.check_call(['rm', '-rf', self.stable_temp])
        subprocess.check_call(['rm', '-rf', self.stable_rc_temp])

    @mock.patch('cvelib.common.do_pull')
    def test_generate_context(self, _):
        """Unit test for generate_context."""
        cg = contextgenerator.ContextGenerator(['v1.0', 'v2.0'])

        cg.generate_context(TestContextGenerator.linux_sha)

        self.assertIn('v1.0', cg.kernels)
        self.assertNotIn('v2.0', cg.kernels)

    def test_get_subject_line(self):
        """Tests that correct subject of given commit is returned."""
        cg = contextgenerator.ContextGenerator([])

        subject = cg.get_subject_line(TestContextGenerator.linux_sha)

        self.assertEqual(subject, TestContextGenerator.linux_subject)

    def test_get_fixes_commit(self):
        """Tests if correct sha from Fixes: tag is returned."""
        cg = contextgenerator.ContextGenerator([])

        fixes_sha = cg.get_fixes_commit(TestContextGenerator.linux_sha)

        # Commit that is refered to by linux_sha in fixes tag.
        expected_sha = '017c59c042d0'

        self.assertEqual(fixes_sha, expected_sha)

    @mock.patch('cvelib.common.do_pull')
    def test_filter_fixed_kernels(self, _):
        """Tests that kernels with same commit as linux_sha are filtered out."""
        cg = contextgenerator.ContextGenerator(['v1.0', 'v2.0'])

        cg.filter_fixed_kernels(TestContextGenerator.linux_sha)

        self.assertIn('v1.0', cg.kernels)
        self.assertNotIn('v2.0', cg.kernels)

    @mock.patch('cvelib.common.do_pull')
    def test_find_kernels_with_fixes_subj(self, _):
        """Tests that kernels without specific fix commit are filtered out."""
        cg = contextgenerator.ContextGenerator(['v1.0', 'v2.0'])

        cg.find_kernels_with_fixes_subj(TestContextGenerator.linux_sha)

        self.assertIn('v1.0', cg.kernels)
        self.assertNotIn('v2.0', cg.kernels)

    def test_detect_relevant_commits(self):
        """Unit test for detect_relevant_commits."""
        cg = contextgenerator.ContextGenerator([])

        # From Linux kernel, used for finding commits whose fixes tag refers to it.
        sha = '14fceff4771e51'

        cg.detect_relevant_commits(sha)

        # Commit's fixes tag refers to 14fceff4771e51.
        self.assertIn('4d3da2d8d91f66988a829a18a0ce59945e8ae4fb', cg.relevant_commits)

    @mock.patch('cvelib.common.do_pull')
    def test_filter_based_on_stable(self, _):
        """Tests that the stable kernels with a given commit are filtered out."""
        # Tests with $STABLE.
        cg = contextgenerator.ContextGenerator(['v1.0', 'v2.0'])

        cg.filter_based_on_stable(TestContextGenerator.linux_sha, os.getenv('STABLE'))

        self.assertIn('v1.0', cg.kernels)
        self.assertNotIn('v2.0', cg.kernels)

        # Tests with $STABLE_RC.
        cg.filter_based_on_stable(TestContextGenerator.linux_sha, os.getenv('STABLE_RC'))

        self.assertIn('v1.0', cg.kernels)
        self.assertNotIn('v2.0', cg.kernels)

    def test_is_in_kernel(self):
        """Tests for properly checking if a given commit is in a given kernel."""
        cg = contextgenerator.ContextGenerator([])

        check = cg.is_in_kernel(self.kernel_temp1, TestContextGenerator.fixes_subject, True)

        self.assertTrue(check)

        check = cg.is_in_kernel(self.kernel_temp2, TestContextGenerator.fixes_subject, True)

        self.assertFalse(check)
