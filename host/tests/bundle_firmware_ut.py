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
import bundle_firmware
import cros_output
from tools import Tools


def GetFlagName(index):
  """Returns the flag name for the given index value (0...n-1)."""
  return bundle_firmware.gbb_flag_properties.keys()[index]

def GetFlagValue(index):
  """Returns the flag value for the given index value (0...n-1)."""
  return bundle_firmware.gbb_flag_properties.values()[index]


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
    self.bundle.SetOptions(False, None)

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
    self.assertRaises(ValueError, self.bundle.SelectFdt, 'tegra-map.dts', True)

  def assertRaisesContains(self, exception, match, func, *args):
    try:
      func(*args)
    except Exception as e:
      if not match in str(e):
        self.fail('Unexpected exception thrown: %s' % str(e))
    else:
      self.fail('IOError not thrown')

  def test_Defaults(self):
    """Test that default handling works correctly."""
    uboot_fname = self.MakeRandomFile(600 * 1024)
    self.bundle.SetFiles('robin_hood', bct=self.bct_fname,
                         uboot=uboot_fname, bmpblk=self.bmpblk_fname)

    # If we don't ask for defaults, we should not get them. This first one
    # raises because it tries to operate on the string None
    self.assertRaises(ValueError, self.bundle.SelectFdt, None, False)

    # This one raises because the file 'fred' does not exist.
    self.assertRaises(IOError, self.bundle.SelectFdt, 'fred', False)

    # Same with this one, but we check the filename.
    self.assertRaisesContains(IOError,
        '/build/robin_hood/firmware/dts/fred.dts', self.bundle.SelectFdt,
        'fred', True)

  def test_TooLarge(self):
    """Test for failure when U-Boot exceeds the size available for it."""
    uboot_fname = self.MakeRandomFile(900 * 1024)
    self.bundle.SetFiles('robin_hood', bct=self.bct_fname,
                         uboot=uboot_fname, bmpblk=self.bmpblk_fname)
    self.bundle.CheckOptions()
    self.bundle.SelectFdt('dts/tegra-map.dts', True)
    image = os.path.join(self.tmpdir, 'image.bin')
    self.assertRaises(ValueError, self.bundle.Start, 'hwid', image, False)

  def test_Normal(self):
    """Test that we get output for a simple case."""
    uboot_fname = self.MakeRandomFile(600 * 1024)
    self.bundle.SetFiles('robin_hood', bct=self.bct_fname,
                         uboot=uboot_fname, bmpblk=self.bmpblk_fname)
    self.bundle.CheckOptions()
    self.bundle.SelectFdt('dts/tegra-map.dts', True)
    image = os.path.join(self.tmpdir, 'image.bin')
    out_fname = self.bundle.Start('hwid', image, False)

    # We expect the size to be 2MB.
    # TODO(sjg@chromium.org): Read this from the fdt file instead.
    self.assertEquals(os.stat(image).st_size, 2 * 1024 * 1024)

  def test_Flags(self):
    bundle = self.bundle
    self.assertEquals(0, bundle.DecodeGBBFlagsFromOptions(0, None))

    # Make sure each flag works.
    all = []
    all_value = 0
    for flag, value in bundle_firmware.gbb_flag_properties.iteritems():
      self.assertEquals(value, bundle.DecodeGBBFlagsFromOptions(0, flag))
      all.append(flag)
      all_value |= value

    # Nop.
    self.assertEquals(23, bundle.DecodeGBBFlagsFromOptions(23, ''))
    self.assertEquals(23, bundle.DecodeGBBFlagsFromOptions(23, None))

    # Starting from 0, try turning on all flags.
    self.assertEquals(all_value,
                      bundle.DecodeGBBFlagsFromOptions(0, ','.join(all)))

    # Starting from the value for all flags on, try turning off all flags.
    all_off = ['-%s' % item for item in bundle_firmware.gbb_flag_properties]
    self.assertEquals(0, bundle.DecodeGBBFlagsFromOptions(all_value,
                                      ','.join(all_off)))

    # Make sure + and - work. Start with a random flag.
    start_value = GetFlagValue(2) | GetFlagValue(3)
    expr = '+%s,+%s,-%s' % (GetFlagName(1), GetFlagName(4), GetFlagName(3))
    expect_value = start_value | GetFlagValue(1) | GetFlagValue(4)
    expect_value &= ~ GetFlagValue(3)
    self.assertEquals(expect_value,
                      bundle.DecodeGBBFlagsFromOptions(start_value, expr))

    # Try hex value
    self.assertEquals(0x69, bundle.DecodeGBBFlagsFromOptions(4, '69'))
    self.assertEquals(0xc, bundle.DecodeGBBFlagsFromOptions(4, 'c'))
    self.assertEquals(0xc, bundle.DecodeGBBFlagsFromOptions(4, '00c'))


if __name__ == '__main__':
  unittest.main()
