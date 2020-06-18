# -*-coding: utf-8 -*-

"""Testing script for cvelib/common.py."""

import unittest
from unittest import mock
import tempfile
import subprocess

from cvelib import common


class TestCommon(unittest.TestCase):
    """Test class for cvelib/common.py."""

    def setUp(self):
        self.temp = tempfile.mkdtemp()
        subprocess.check_call(['git', 'init'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              cwd=self.temp)

        subprocess.check_call(['git', 'checkout', '-b', 'branch-1.0'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.temp)
        subprocess.check_call(['touch', 'file1'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.temp)
        subprocess.check_call(['git', 'add', 'file1'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.temp)
        subprocess.check_call(['git', 'commit', '-m', 'random commit'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.temp)

        subprocess.check_call(['git', 'checkout', '-b', 'branch-2.0'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.temp)

    @mock.patch('cvelib.common.do_pull')
    def test_checkout_branch(self, _):
        """Unit test for checkout_branch."""
        kernel = 'v1.0'

        common.checkout_branch(kernel, 'branch-1.0', 'origin', 'branch-1.0', self.temp)

        # Outputs the current branch.
        branch = subprocess.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'],
                                         stderr=subprocess.DEVNULL, cwd=self.temp)

        self.assertEqual(branch.rstrip(), b'branch-1.0')
