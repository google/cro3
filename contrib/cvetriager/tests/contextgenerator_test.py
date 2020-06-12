# -*-coding: utf-8 -*-

"""Testing script for cvelib/contextgenerator.py"""

import unittest
from unittest import mock
import tempfile
import subprocess
import os

from cvelib import contextgenerator

class TestContextGenerator(unittest.TestCase):
    """Test class for cvelib/contextgenerator.py"""

    def setUp(self):
        # Backup $CHROMIUMOS_KERNEL
        self.cros_kernel = os.getenv('CHROMIUMOS_KERNEL')

        # Make temporary directory for $CHROMIUMOS_KERNEL
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

        fixes_subject = 'relay: Use per CPU constructs for the relay channel buffer pointers'

        # Adds commit to v1.0 with expected commit subject
        subprocess.check_call(['touch', 'new_file'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.kernel_temp1)
        subprocess.check_call(['git', 'add', 'new_file'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.kernel_temp1)
        subprocess.check_call(['git', 'commit', '-m', fixes_subject], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.kernel_temp1)

        linux_subject = 'kernel/relay.c: handle alloc_percpu returning NULL in relay_open'

        # Helps test the filtering out of an already fixed kernel
        subprocess.check_call(['touch', 'new_file2'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.kernel_temp2)
        subprocess.check_call(['git', 'add', 'new_file2'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.kernel_temp2)
        subprocess.check_call(['git', 'commit', '-m', linux_subject], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.kernel_temp2)

    def tearDown(self):
        if self.cros_kernel:
            os.environ['CHROMIUMOS_KERNEL'] = self.cros_kernel
        else:
            del os.environ['CHROMIUMOS_KERNEL']

        subprocess.check_call(['rm', '-rf', self.cros_temp])

    @mock.patch('cvelib.patchapplier.checkout_branch')
    def test_generate_context(self, _):
        """Unit test for generate_context"""
        cg = contextgenerator.ContextGenerator(['v1.0', 'v2.0'])

        linux_sha = '54e200ab40fc14c863bcc80a51e20b7906608fce'

        cg.generate_context(linux_sha)

        self.assertIn('v1.0', cg.kernels)
        self.assertNotIn('v2.0', cg.kernels)

    def test_get_subject_line(self):
        """Unit test for get_subject_line"""
        cg = contextgenerator.ContextGenerator([])

        sha = '54e200ab40fc14c863bcc80a51e20b7906608fce'

        subject = cg.get_subject_line(sha)

        expected_subject = 'kernel/relay.c: handle alloc_percpu returning NULL in relay_open'

        self.assertEqual(subject, expected_subject)

    def test_get_fixes_commit(self):
        """Unit test for get_fixes_commit"""
        cg = contextgenerator.ContextGenerator([])

        sha = '54e200ab40fc14c863bcc80a51e20b7906608fce'

        fixes_sha = cg.get_fixes_commit(sha)

        expected_sha = '017c59c042d0'

        self.assertEqual(fixes_sha, expected_sha)

    @mock.patch('cvelib.patchapplier.checkout_branch')
    def test_filter_fixed_kernels(self, _):
        """Unit test for filter_fixed_kernels"""
        cg = contextgenerator.ContextGenerator(['v1.0', 'v2.0'])

        sha = '54e200ab40fc14c863bcc80a51e20b7906608fce'

        cg.filter_fixed_kernels(sha)

        self.assertIn('v1.0', cg.kernels)
        self.assertNotIn('v2.0', cg.kernels)

    @mock.patch('cvelib.patchapplier.checkout_branch')
    def test_find_kernels_with_fixes_subj(self, _):
        """Unit test for find_kernels_with_fixes_subj"""
        cg = contextgenerator.ContextGenerator(['v1.0', 'v2.0'])

        sha = '54e200ab40fc14c863bcc80a51e20b7906608fce'

        cg.find_kernels_with_fixes_subj(sha)

        self.assertIn('v1.0', cg.kernels)
        self.assertNotIn('v2.0', cg.kernels)

    def test_detect_relevant_commits(self):
        """Unit test for detect_relevant_commits"""
        cg = contextgenerator.ContextGenerator([])

        sha = '14fceff4771e51'

        cg.detect_relevant_commits(sha)

        self.assertIn('4d3da2d8d91f66988a829a18a0ce59945e8ae4fb', cg.relevant_commits)
