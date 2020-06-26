# -*-coding: utf-8 -*-

"""Testing script for cvelib/clgenerator.py."""

import unittest
from unittest import mock
import tempfile
import subprocess
import os

from cvelib import clgenerator


class TestCLGenerator(unittest.TestCase):
    """Test class for cvelib/clgenerator.py."""

    cl_links = ['https://chromium-review.googlesource.com/c/chromiumos/platform/dev-util/+/2268097',
                'https://chromium-review.googlesource.com/c/chromiumos/platform/dev-util/+/1234567']

    sample_push_msg = ('Enumerating objects: 33, done.\n'
                       'Counting objects: 100% (33/33), done.\n'
                       'Delta compression using up to 16 threads\n'
                       'Compressing objects: 100% (24/24), done.\n'
                       'Writing objects: 100% (24/24), 6.44 KiB | 2.15 MiB/s, done.\n'
                       'Total 24 (delta 16), reused 0 (delta 0), pack-reused 0\n'
                       'remote: Resolving deltas: 100% (16/16)\n'
                       'remote: Processing changes: refs: 1, new: 1, done    \n'
                       'remote: \n'
                       'remote: SUCCESS\n'
                       'remote: \n'
                       'remote:   ' + cl_links[0] + ' only made to get sample push output [NEW]\n'
                       'remote:   ' + cl_links[1] + ' fake second CL\n'
                       'remote: \n'
                       'To https://chromium.googlesource.com/chromiumos/platform/dev-util\n'
                       '* [new branch]                HEAD -> refs/for/master\n')

    def setUp(self):
        # Backup of CHROMIUMOS_KERNEL.
        self.cros_kernel = os.getenv('CHROMIUMOS_KERNEL')

        # Make temporary directory for $CHROMIUMOS_KERNEL.
        self.cros_temp = tempfile.mkdtemp()
        os.environ['CHROMIUMOS_KERNEL'] = self.cros_temp
        self.kernel_temp1 = os.path.join(self.cros_temp, 'v1.0')
        os.mkdir(self.kernel_temp1)
        subprocess.check_call(['git', 'init'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.kernel_temp1)

        subprocess.check_call(['git', 'checkout', '-b', 'b123-v1.0'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              cwd=self.kernel_temp1)
        subprocess.check_call(['touch', 'random_file'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.kernel_temp1)
        subprocess.check_call(['git', 'add', 'random_file'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.kernel_temp1)
        subprocess.check_call(['git', 'commit', '-m', 'random'], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, cwd=self.kernel_temp1)

    def tearDown(self):
        if self.cros_kernel:
            os.environ['CHROMIUMOS_KERNEL'] = self.cros_kernel
        else:
            del os.environ['CHROMIUMOS_KERNEL']

        subprocess.check_call(['rm', '-rf', self.cros_temp])

    @mock.patch('cvelib.clgenerator.do_push', return_value=sample_push_msg)
    def test_create_cls(self, _):
        """Tests that CL was properly created."""
        bug_id = '123'
        kernels = ['v1.0']

        output = clgenerator.create_cls(bug_id, kernels)

        expected_map = {'v1.0': TestCLGenerator.cl_links}

        self.assertEqual(output, expected_map)

    def test_get_git_push_cmd(self):
        """Tests if push command is correct."""
        output = clgenerator.get_git_push_cmd('v1.0')

        expected = 'git push cros HEAD:refs/for/chromeos-1.0'

        self.assertEqual(output, expected)

    def test_parse_cls_output(self):
        """Tests if CL link was properly picked from push output."""
        links = clgenerator.parse_cls_output(TestCLGenerator.sample_push_msg)

        self.assertEqual(links, TestCLGenerator.cl_links)
