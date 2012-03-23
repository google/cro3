#!/usr/bin/python

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This contains tests for bundle_firmware using the unittest framework.

It supports creating a few images so far, but the testing is very basic.
"""

import collections
import os
import shutil
import unittest
import tempfile

from bundle_firmware import Bundle
import cros_output
from tools import Tools


class TestBundleFirmware(unittest.TestCase):
  """Unit test class for bundle_firmware.py."""

  def setUp(self):
    """Set up filenames for running the test.

    A fake U-Boot binary is created ready for use in tests.
    """
    self._file_upto = 0         # How many files we have created
    self.tmpdir = tempfile.mkdtemp()
    self.output = cros_output.Output()
    self.tools = Tools(self.output)
    self.tools.PrepareOutputDir(None)
    self.bundle = Bundle(self.tools, self.output)
    self.uboot_fname = self.MakeRandomFile(500 * 1024)
    self.bmpblk_fname = os.path.abspath('bin/bmpblk.bin')
    self.bct_fname = os.path.abspath('bin/board.bct')
    self.bundle.SetDirs('##/usr/share/vboot/devkeys')

  def tearDown(self):
    """Clean up after completion of tests."""
    del self.bundle

    # Delete the temporary directory created by the tools object.
    self.tools.FinalizeOutputDir()
    del self.tools
    del self.output
    shutil.rmtree(self.tmpdir)

  def TmpName(self, file_num):
    """Returns a suitable filename for the given temporary file number.

    Args:
      file_num: The temporary file number (0 is the first).

    Returns:
      The filenme of the file_num'th file.
    """
    return os.path.join(self.tmpdir, '%02d.bin' % file_num)

  def MakeRandomFile(self, size):
    """Make a file of the given size, and fill it with pseudo-random data.

    The file will be created in the 'bin' directory.

    Uses the contents of lorem.txt from here:
      http://desktoppub.about.com/library/weekly/lorem.txt

    Based on an algorithm here:

      http://jessenoller.com/2008/05/30/making-re-creatable-
          random-data-files-really-fast-in-python/

    Args:
      size: Size of file to create, in bytes.

    Returns:
      Absolute path to the created file.
    """
    fname = os.path.abspath(self.TmpName(self._file_upto))
    self._file_upto += 1
    with open(fname, 'wb') as fd:
      seed = '1092384956781341341234656953214543219'
      words = open('lorem.txt', 'r').read().split()

      def _GetData():
        """Continuously yield the next 1024 bytes of data."""
        a = collections.deque(words)
        b = collections.deque(seed)
        while True:
          yield ' '.join(list(a)[0:1024])
          a.rotate(int(b[0]))
          b.rotate(1)

      get_data = _GetData()
      upto = 0
      while upto < size:
        data = get_data.next()
        todo = min(size - upto, len(data))
        fd.write(data[:todo])
        upto += todo

    return fname

  # pylint: disable=W0212,C6409
  def test_NoBoard(self):
    """With no board selected, it should fail."""
    self.assertRaises(ValueError, self.bundle.SelectFdt, 'tegra-map.dts')

  def test_TooLarge(self):
    """Test for failure when U-Boot exceeds the size available for it."""
    uboot_fname = self.MakeRandomFile(900 * 1024)
    self.bundle.SetFiles('robin_hood', bct=self.bct_fname,
                         uboot=uboot_fname, bmpblk=self.bmpblk_fname)
    self.bundle.SelectFdt('dts/tegra-map.dts')
    image = os.path.join(self.tmpdir, 'image.bin')
    self.assertRaises(ValueError, self.bundle.Start, 'hwid', image, False)

  def test_Normal(self):
    """Test that we get output for a simple case."""
    uboot_fname = self.MakeRandomFile(600 * 1024)
    self.bundle.SetFiles('robin_hood', bct=self.bct_fname,
                         uboot=uboot_fname, bmpblk=self.bmpblk_fname)
    self.bundle.SelectFdt('dts/tegra-map.dts')
    image = os.path.join(self.tmpdir, 'image.bin')
    out_fname = self.bundle.Start('hwid', image, False)

    # We expect the size to be 2MB.
    # TODO(sjg@chromium.org): Read this from the fdt file instead.
    self.assertEquals(os.stat(image).st_size, 2 * 1024 * 1024)

if __name__ == '__main__':
  unittest.main()
