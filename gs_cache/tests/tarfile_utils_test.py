# -*- coding: utf-8 -*-
# Copyright 2018 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for tarfile_utils."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import StringIO
import subprocess
import tarfile
import unittest

import tarfile_utils


class TarfileUtilsTest(unittest.TestCase):
  """Tests of tarfile_utils."""

  def test_list_tar_members_empty_file(self):
    """Test listing file member of an empty tar."""
    tar_tvR = StringIO.StringIO('block 0: ** Block of NULs **\n')
    self.assertFalse(list(tarfile_utils.list_tar_members(tar_tvR)))

  def test_list_tar_members_non_empty_file(self):
    """Test listing file member of an non-empty tar."""
    tar_tvR = StringIO.StringIO(
        'block 0: mode owner 1 date hour:min\tfilename\n'
        'block 2: mode owner 123 date hour:min\tfile name with spaces\n'
        'block 4: mode owner 0 date hour:min\tdirectory/\n'
        'block 5: mode owner 0 date hour:min\tdirectory/symbol link -> filename'
        '\n'
        'block 6: ** Block of NULs **\n'
    )
    result = list(tarfile_utils.list_tar_members(tar_tvR))
    self.assertEqual(result, [
        ('filename', 0, 1024, 512, 1),
        ('file name with spaces', 512 * 2, 1024, 512 * 3, 123),
        ('directory/', 512 * 4, 512, 512 * 5, 0),
        ('directory/symbol link -> filename', 512 * 5, 512, 512 * 6, 0)
    ])

  def test_list_tar_member_with_real_tar_file(self):
    """Using a real tar file to test listing tar member."""
    tar_name = os.path.join(os.path.dirname(__file__),
                            'index_tar_member_testing.tgz')
    tar_tvR = StringIO.StringIO(
        subprocess.check_output(['tar', 'tvRzf', tar_name]))
    members = tarfile_utils.list_tar_members(tar_tvR)
    with tarfile.open(tar_name, 'r:gz') as tar:
      for tar_info, result in zip(tar, members):
        if tar_info.isreg():
          name = tar_info.name

        if tar_info.isdir():
          name = '%s/' % tar_info.name

        if tar_info.issym():
          name = '%s -> %s' % (tar_info.name, tar_info.linkname)

        self.assertEqual(name, result.filename)
        self.assertEqual(tar_info.offset_data, result.content_start)
        self.assertEqual(tar_info.size, result.size)


if __name__ == '__main__':
  unittest.main()
