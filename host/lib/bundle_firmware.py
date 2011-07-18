# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module builds a firmware image for a tegra-based board.

This modules uses a few rudimentary other libraries for its activity.

Here are the names we give to the various files we deal with. It is important
to keep these consistent!

  uboot     u-boot.bin (with no device tree)
  fdt       the fdt blob
  bct       the BCT file
  bootstub  uboot + fdt
  signed    (uboot + fdt + bct) signed blob
"""

import os
import re

import cros_output
from fdt import Fdt
from pack_firmware import PackFirmware
import shutil
import tempfile
from tools import Tools
from write_firmware import WriteFirmware

# This data is required by bmpblk_utility. Does it ever change?
# It was stored with the chromeos-bootimage ebuild, but we want
# this utility to work outside the chroot.
yaml_data = '''
bmpblock: 1.0

images:
    devmode:    DeveloperBmp/DeveloperBmp.bmp
    recovery:   RecoveryBmp/RecoveryBmp.bmp
    rec_yuck:   RecoveryNoOSBmp/RecoveryNoOSBmp.bmp
    rec_insert: RecoveryMissingOSBmp/RecoveryMissingOSBmp.bmp

screens:
  dev_en:
    - [0, 0, devmode]
  rec_en:
    - [0, 0, recovery]
  yuck_en:
    - [0, 0, rec_yuck]
  ins_en:
    - [0, 0, rec_insert]

localizations:
  - [ dev_en, rec_en, yuck_en, ins_en ]
'''

class Bundle:
  """This class encapsulates the entire bundle firmware logic."""

  def __init__(self, options, args):
    self.options = options
    self.args = args
    self._out = cros_output.Output(options.verbosity)

  def __del__(self):
    self._out.ClearProgress()

  def _CheckOptions(self):
    """Check provided options and select defaults."""
    options = self.options
    build_root = os.path.join('##', 'build', options.board, 'u-boot')
    if not options.fdt:
      options.fdt = os.path.join(build_root, 'dtb', '%s.dtb' %
          re.sub('_', '-', options.board))
    if not options.uboot:
      options.uboot = os.path.join(build_root, 'u-boot.bin')
    if not options.bct:
      options.bct = os.path.join(build_root, 'bct', 'board.bct')

  def _CheckTools(self):
    """Check that all required tools are present.

    Raises:
      CmdError if a required tool is not found.
    """
    if self.options.write:
      self._tools.CheckTool('nvflash')
    self._tools.CheckTool('dtput', 'dtc')
    self._tools.CheckTool('dtget', 'dtc')

  def _CreateGoogleBinaryBlock(self):
    """Create a GBB for the image.

    Returns:
      Path of the created GBB file.

    Raises:
      CmdError if a command fails.
    """
    hwid = self.fdt.GetString('/config/hwid')
    gbb_size = self.fdt.GetFlashPartSize('ro', 'gbb')
    dir = self._tools.outdir

    # Get LCD dimensions from the device tree.
    screen_geometry = '%sx%s' % (self.fdt.GetInt('/lcd/width'),
        self.fdt.GetInt('/lcd/height'))

    # This is the magic directory that make_bmp_image writes to!
    out_dir = 'out_%s' % re.sub(' ', '_', hwid)
    bmp_dir = os.path.join(dir, out_dir)
    self._out.Progress('Creating bitmaps')
    self._tools.Run('make_bmp_image', [hwid, screen_geometry, 'arm'], cwd=dir)

    self._out.Progress('Creating bitmap block')
    yaml = 'config.yaml'
    self._tools.WriteFile(os.path.join(bmp_dir, yaml), yaml_data)
    self._tools.Run('bmpblk_utility', ['-z', '2', '-c', yaml, 'bmpblk.bin'],
        cwd=bmp_dir)

    self._out.Progress('Creating GBB')
    sizes = [0x100, 0x1000, gbb_size - 0x2180, 0x1000]
    sizes = ['%#x' % size for size in sizes]
    gbb = 'gbb.bin'
    keydir = self._tools.Filename(self.options.key)
    self._tools.Run('gbb_utility', ['-c', ','.join(sizes), gbb], cwd=dir)
    self._tools.Run('gbb_utility', ['-s',
        '--hwid=%s' % hwid,
        '--rootkey=%s/root_key.vbpubk' % keydir,
        '--recoverykey=%s/recovery_key.vbpubk' % keydir,
        '--bmpfv=%s' % os.path.join(out_dir, 'bmpblk.bin'),
        gbb],
        cwd=dir)
    return os.path.join(dir, gbb)

  def _SignBootstub(self, bct, bootstub, text_base, name):
    """Sign an image so that the Tegra SOC will boot it.

    Args:
      bct: BCT file to use.
      bootstub: Boot stub (U-Boot + fdt) file to sign.
      text_base: Address of text base for image.
      name: root of basename to use for signed image.

    Returns:
      filename of signed image.

    Raises:
      CmdError if a command fails.
    """
    # First create a config file - this is how we instruct cbootimage
    signed = os.path.join(self._tools.outdir, 'signed%s.bin' % name)
    self._out.Progress('Signing Bootstub')
    config = os.path.join(self._tools.outdir, 'boot%s.cfg' % name)
    fd = open(config, 'w')
    fd.write('Version    = 1;\n')
    fd.write('Redundancy = 1;\n')
    fd.write('Bctfile    = %s;\n' % bct)
    fd.write('BootLoader = %s,%#x,%#x,Complete;\n' % (bootstub, text_base,
        text_base))
    fd.close()

    self._tools.Run('cbootimage', [config, signed])
    self._tools.OutputSize('BCT', bct)
    self._tools.OutputSize('Signed image', signed)
    return signed

  def _PrepareFdt(self, fdt):
    """Prepare an fdt with any additions selected, and return its contents.

    Args:
      fdt: Input fdt filename

    Returns:
      String containing new fdt, after adding boot command, etc.
    """
    fdt = self.fdt.Copy(os.path.join(self._tools.outdir, 'updated.dtb'))
    if self.options.bootcmd:
      fdt.PutString('/config/bootcmd', self.options.bootcmd)
      self._out.Info('Boot command: %s' % self.options.bootcmd)
    if self.options.add_config_str:
      for config in self.options.add_config_str:
        fdt.PutString('/config/%s' % config[0], config[1])
    if self.options.add_config_int:
      for config in self.options.add_config_int:
        try:
          value = int(config[1])
        except ValueError as str:
          raise CmdError("Cannot convert config option '%s' to integer" %
              config[1])
        fdt.PutInteger('/config/%s' % config[0], value)
    return self._tools.ReadFile(fdt.fname)

  def _CreateBootStub(self, uboot, fdt, text_base):
    """Create a boot stub and a signed boot stub.

    Args:
      uboot: Path to u-boot.bin (may be chroot-relative)
      fdt: A Fdt object to use as the base Fdt
      text_base: Address of text base for image.

    Returns:
      Tuple containing:
        Full path to u-boot.bin.
        Full path to bootstub.

    Raises:
      CmdError if a command fails.
    """
    options = self.options
    uboot_data = self._tools.ReadFile(uboot)
    fdt_data = self._PrepareFdt(fdt)
    bootstub = os.path.join(self._tools.outdir, 'u-boot-fdt.bin')
    self._tools.WriteFile(bootstub, uboot_data + fdt_data)
    self._tools.OutputSize('U-Boot binary', options.uboot)
    self._tools.OutputSize('U-Boot fdt', options.fdt)
    self._tools.OutputSize('Combined binary', bootstub)

    # sign the bootstub; this is a combination of the board specific
    # bct and the stub u-boot image.
    signed = self._SignBootstub(self._tools.Filename(options.bct), bootstub,
        text_base, '')
    return self._tools.Filename(uboot), bootstub, signed

  def _PackOutput(self, msg):
    """Helper function to write output from PackFirmware (verbose level 2).

    This is passed to PackFirmware for it to use to write output.

    Args:
      msg: Message to display.
    """
    self._out.Notice(msg)

  def _CreateImage(self, gbb, text_base):
    """Create a full firmware image, along with various by-products.

    This uses the provided u-boot.bin, fdt and bct to create a firmware
    image containing all the required parts. If the GBB is not supplied
    then this will just return a signed U-Boot as the image.

    Args:
      gbb       Full path to the GBB file, or empty if a GBB is not required.
      text_base: Address of text base for image.

    Raises:
      CmdError if a command fails.
    """

    options = self.options
    self._out.Notice("Model: %s" % self.fdt.GetString('/model'))

    # Create the boot stub, which is U-Boot plus an fdt and bct
    uboot, bootstub, signed = self._CreateBootStub(options.uboot,
        self.fdt, text_base)

    if gbb:
      pack = PackFirmware(self._tools, self._out)
      image = os.path.join(self._tools.outdir, 'image.bin')
      fwid = self._tools.GetChromeosVersion()
      self._out.Notice('Firmware ID: %s' % fwid)
      pack.SetupFiles(boot=bootstub, signed=signed, gbb=gbb,
          fwid=fwid, keydir=options.key)
      pack.SelectFdt(self.fdt)
      pack.PackImage(self._tools.outdir, image)
    else:
      image = signed

    self._tools.OutputSize('Final image', image)
    return uboot, image

  def Start(self):
    """This performs all the requested operations for this script.

      - Checks options, tools, output directory, fdt.
      - Creates GBB and image.
      - Writes image to board.
    """
    options = self.options
    self._CheckOptions()
    self._tools = Tools(self._out)
    self._CheckTools()

    self._tools.PrepareOutputDir(options.outdir, options.preserve)
    self.fdt = Fdt(self._tools, options.fdt)

    text_base = self.fdt.GetInt('/chromeos-config/textbase');
    gbb = ''
    if not options.small:
      gbb = self._CreateGoogleBinaryBlock()

    # This creates the actual image.
    uboot, image = self._CreateImage(gbb, text_base)
    if options.output:
      shutil.copyfile(image, options.output)
      self._out.Notice("Output image '%s'" % options.output)

    # Write it to the board if required.
    if options.write:
      write = WriteFirmware(self._tools, self.fdt, self._out, text_base)
      if write.FlashImage(uboot, options.bct, image):
        self._out.Progress('Image uploaded - please wait for flashing to '
            'complete')
      else:
        raise CmdError('Image upload failed - please check board connection')
