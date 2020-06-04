# -*-coding: utf-8 -*-

"""This is a testing script for cvelib/patchapplier.py"""

import unittest
from unittest import mock
import tempfile
import subprocess
import os

from cvelib import patchapplier as pa

class TestCVETriager(unittest.TestCase):
    """Handles test cases for cvelib/patchapplier.py"""

    def setUp(self):

        # Backup $LINUX and $CHROMIUMOS_KERNEL
        self.linux = os.getenv('LINUX')
        self.cros_kernel = os.getenv('CHROMIUMOS_KERNEL')

        # Make temporary directory for $LINUX
        self.linux_temp = tempfile.mkdtemp()
        os.environ['LINUX'] = self.linux_temp
        subprocess.check_call(['git', 'init'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              cwd=os.getenv('LINUX'))

        for i in range(1, 4):
            subprocess.check_call(['touch', str(i)], cwd=os.getenv('LINUX'))
            subprocess.check_call(['git', 'add', str(i)], cwd=os.getenv('LINUX'))
            subprocess.check_call(['git', 'commit', '-m', str(i)], stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, cwd=os.getenv('LINUX'))

        # Clone LINUX to CHROMIUMOS_KERNEL
        self.cros_temp = tempfile.mkdtemp()
        os.environ['CHROMIUMOS_KERNEL'] = self.cros_temp
        subprocess.check_call(['git', 'clone', self.linux_temp], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=os.getenv('CHROMIUMOS_KERNEL'))

        # Add extra commit to LINUX
        subprocess.check_call(['touch', '4'], cwd=os.getenv('LINUX'))
        subprocess.check_call(['git', 'add', '4'], cwd=os.getenv('LINUX'))
        subprocess.check_call(['git', 'commit', '-m', '4'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=os.getenv('LINUX'))

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

    @mock.patch('cvelib.patchapplier.checkout_branch')
    def test_apply_patch(self, _):
        """Unit test for apply_patch"""

        sha = pa.get_sha(self.linux_temp)
        bug_id = '123'
        kernel_versions = [os.path.basename(self.linux_temp)]

        kernels = pa.apply_patch(sha, bug_id, kernel_versions)

        self.assertTrue(kernels[os.path.basename(self.linux_temp)])

    def test_create_commit_message(self):
        """Unit test for create_commit_message"""

        kernel = os.path.basename(self.linux_temp)
        kernel_path = os.path.join(os.getenv('CHROMIUMOS_KERNEL'), kernel)

        sha = pa.get_sha(self.linux_temp)
        bug_id = '123'

        pa.fetch_linux_kernel(kernel_path)

        pa.cherry_pick(kernel_path, sha, bug_id)

        # Retrieves new cherry-picked message
        msg = pa.get_commit_message(kernel_path, pa.get_sha(kernel_path))

        check = False
        if 'UPSTREAM:' in msg and 'BUG=' in msg and 'TEST=' in msg:
            check = True

        self.assertTrue(check)

    def test_fetch_linux_kernel(self):
        """Unit test for fetch_linux_kernel"""

        kernel = os.path.basename(self.linux_temp)
        kernel_path = os.path.join(os.getenv('CHROMIUMOS_KERNEL'), kernel)

        linux_expected = self.linux_temp

        linux_actual = pa.fetch_linux_kernel(kernel_path)

        # Checks if fetched from the correct repo
        self.assertEqual(linux_expected, linux_actual)

    def test_cherry_pick(self):
        """Unit test for cherry_pick"""

        kernel = os.path.basename(self.linux_temp)
        kernel_path = os.path.join(os.getenv('CHROMIUMOS_KERNEL'), kernel)

        sha = pa.get_sha(self.linux_temp)
        bug_id = '123'

        pa.fetch_linux_kernel(kernel_path)

        check = pa.cherry_pick(kernel_path, sha, bug_id)

        self.assertTrue(check)

    @mock.patch('cvelib.patchapplier.checkout_branch')
    def test_invalid_sha(self, _):
        """Test for passing of invalid commit sha"""

        sha = '123'
        bug = '123'
        kernel_versions = [os.path.basename(self.linux_temp)]

        self.assertRaises(pa.PatchApplierException, pa.apply_patch,
                          sha, bug, kernel_versions)

    def test_invalid_linux_path(self):
        """Test for invalid LINUX directory"""

        linux = os.getenv('LINUX')
        os.environ['LINUX'] = '/tmp/tmp'

        kernel = os.path.basename(self.linux_temp)
        kernel_path = os.path.join(os.getenv('CHROMIUMOS_KERNEL'), kernel)

        self.assertRaises(pa.PatchApplierException, pa.fetch_linux_kernel,
                          kernel_path)

        os.environ['LINUX'] = linux

    def test_empty_env_variables(self):
        """Test for empty LINUX or CHROMIUMOS_KERNEL environement variables"""

        linux = os.getenv('LINUX')
        chros_kernel = os.getenv('CHROMIUMOS_KERNEL')

        sha = pa.get_sha(self.linux_temp)
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
        """Test for passing of invalid kernel"""

        sha = pa.get_sha(self.linux_temp)
        bug = '123'
        kernel_versions = ['not_a_kernel']

        self.assertRaises(pa.PatchApplierException, pa.apply_patch,
                          sha, bug, kernel_versions)
