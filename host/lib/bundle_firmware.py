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
import struct
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
  """This class encapsulates the entire bundle firmware logic.

  Sequence of events:
    bundle = Bundle(tools.Tools(), cros_output.Output())
    bundle.SetDirs(...)
    bundle.SetFiles(...)
    bundle.SetOptions(...)
    bundle.SelectFdt(fdt.Fdt('filename.dtb')
    .. can call bundle.AddConfigList() if required
    bundle.Start(...)

  Public properties:
    fdt: The fdt object that we use for building our image. This wil be the
        one specified by the user, except that we might add config options
        to it. This is set up by SelectFdt() which must be called before
        bundling starts.
    uboot_fname: Full filename of the U-Boot binary we use.
    bct_fname: Full filename of the BCT file we use.
  """

  def __init__(self, tools, output):
    """Set up a new Bundle object.

    Args:
      tools: A tools.Tools object to use for external tools.
      output: A cros_output.Output object to use for program output.
    """
    self._tools = tools
    self._out = output

    # Set up the things we need to know in order to operate.
    self._board = None          # Board name, e.g. tegra2_seaboard.
    self._fdt_fname = None      # Filename of our FDT.
    self.uboot_fname = None     # Filename of our U-Boot binary.
    self.bct_fname = None       # Filename of our BCT file.
    self.fdt = None             # Our Fdt object.
    self.bmpblk_fname = None    # Filename of our Bitmap Block
    self.coreboot_fname = None  # Filename of our coreboot binary.
    self.seabios_fname = None   # Filename of our SeaBIOS payload.

  def SetDirs(self, keydir):
    """Set up directories required for Bundle.

    Args:
      keydir: Directory containing keys to use for signing firmware.
    """
    self._keydir = keydir

  def SetFiles(self, board, bct, uboot=None, bmpblk=None, coreboot=None,
               postload=None, seabios=None):
    """Set up files required for Bundle.

    Args:
      board: The name of the board to target (e.g. tegra2_seaboard).
      uboot: The filename of the u-boot.bin image to use.
      bct: The filename of the binary BCT file to use.
      bmpblk: The filename of bitmap block file to use.
      coreboot: The filename of the coreboot image to use (on x86)
      postload: The filename of the u-boot-post.bin image to use.
      seabios: The filename of the SeaBIOS payload to use if any.
    """
    self._board = board
    self.uboot_fname = uboot
    self.bct_fname = bct
    self.bmpblk_fname = bmpblk
    self.coreboot_fname = coreboot
    self.postload_fname = postload
    self.seabios_fname = seabios

  def SetOptions(self, small):
    """Set up options supported by Bundle.

    Args:
      small: Only create a signed U-Boot - don't produce the full packed
          firmware image. This is useful for devs who want to replace just the
          U-Boot part while keeping the keys, gbb, etc. the same.
    """
    self._small = small

  def CheckOptions(self):
    """Check provided options and select defaults."""
    if not self._board:
      raise ValueError('No board defined - please define a board to use')
    build_root = os.path.join('##', 'build', self._board, 'firmware')
    if not self._fdt_fname:
      self._fdt_fname = os.path.join(build_root, 'dts', '%s.dts' %
          re.sub('_', '-', self._board))
    if not self.uboot_fname:
      self.uboot_fname = os.path.join(build_root, 'u-boot.bin')
    if not self.bct_fname:
      self.bct_fname = os.path.join(build_root, 'bct', 'board.bct')
    if not self.bmpblk_fname:
      self.bmpblk_fname = os.path.join(build_root, 'default.bmpblk')

  def _CreateGoogleBinaryBlock(self, hardware_id):
    """Create a GBB for the image.

    Args:
      hardware_id: Hardware ID to use for this board. If None, then the
          default from the Fdt will be used

    Returns:
      Path of the created GBB file.

    Raises:
      CmdError if a command fails.
    """
    if not hardware_id:
      hardware_id = self.fdt.GetString('/config', 'hwid')
    gbb_size = self.fdt.GetFlashPartSize('ro', 'gbb')
    odir = self._tools.outdir

    chromeos_config = self.fdt.GetProps("/chromeos-config")
    if 'fast-developer-mode' not in chromeos_config:
      gbb_flags = 0
    else:
      self._out.Notice("Enabling fast-developer-mode.")
      gbb_flags = 1

    self._out.Progress('Creating GBB')
    sizes = [0x100, 0x1000, gbb_size - 0x2180, 0x1000]
    sizes = ['%#x' % size for size in sizes]
    gbb = 'gbb.bin'
    keydir = self._tools.Filename(self._keydir)
    self._tools.Run('gbb_utility', ['-c', ','.join(sizes), gbb], cwd=odir)
    self._tools.Run('gbb_utility', ['-s',
        '--hwid=%s' % hardware_id,
        '--rootkey=%s/root_key.vbpubk' % keydir,
        '--recoverykey=%s/recovery_key.vbpubk' % keydir,
        '--bmpfv=%s' % self._tools.Filename(self.bmpblk_fname),
        '--flags=%d' % gbb_flags,
        gbb],
        cwd=odir)
    return os.path.join(odir, gbb)

  def _SignBootstub(self, bct, bootstub, text_base):
    """Sign an image so that the Tegra SOC will boot it.

    Args:
      bct: BCT file to use.
      bootstub: Boot stub (U-Boot + fdt) file to sign.
      text_base: Address of text base for image.

    Returns:
      filename of signed image.

    Raises:
      CmdError if a command fails.
    """
    # First create a config file - this is how we instruct cbootimage
    signed = os.path.join(self._tools.outdir, 'signed.bin')
    self._out.Progress('Signing Bootstub')
    config = os.path.join(self._tools.outdir, 'boot.cfg')
    fd = open(config, 'w')
    fd.write('Version    = 1;\n')
    fd.write('Redundancy = 1;\n')
    fd.write('Bctfile    = %s;\n' % bct)

    # TODO(dianders): Right now, we don't have enough space in our flash map
    # for two copies of the BCT when we're using NAND, so hack it to 1.  Not
    # sure what this does for reliability, but at least things will fit...
    is_nand = "NvBootDevType_Nand" in self._tools.Run('bct_dump', [bct])
    if is_nand:
      fd.write('Bctcopy = 1;\n')

    fd.write('BootLoader = %s,%#x,%#x,Complete;\n' % (bootstub, text_base,
        text_base))

    fd.close()

    self._tools.Run('cbootimage', [config, signed])
    self._tools.OutputSize('BCT', bct)
    self._tools.OutputSize('Signed image', signed)
    return signed

  def SetBootcmd(self, bootcmd, bootsecure):
    """Set the boot command for U-Boot.

    Args:
      bootcmd: Boot command to use, as a string (if None this this is a nop).
      bootsecure: We'll set '/config/bootsecure' to 1 if True and 0 if False.
    """
    if bootcmd:
      self.fdt.PutString('/config', 'bootcmd', bootcmd)
      self.fdt.PutInteger('/config', 'bootsecure', int(bootsecure))
      self._out.Info('Boot command: %s' % bootcmd)

  def AddConfigList(self, config_list, use_int=False):
    """Add a list of config items to the fdt.

    Normally these values are written to the fdt as strings, but integers
    are also supported, in which case the values will be converted to integers
    (if necessary) before being stored.

    Args:
      config_list: List of (config, value) tuples to add to the fdt. For each
          tuple:
              config: The fdt node to write to will be /config/<config>.
              value: An integer or string value to write.
      use_int: True to only write integer values.

    Raises:
      CmdError: if a value is required to be converted to integer but can't be.
    """
    if config_list:
      for config in config_list:
        value = config[1]
        if use_int:
          try:
            value = int(value)
          except ValueError as str:
            raise CmdError("Cannot convert config option '%s' to integer" %
                value)
        if type(value) == type(1):
          self.fdt.PutInteger('/config', '%s' % config[0], value)
        else:
          self.fdt.PutString('/config', '%s' % config[0], value)

  def DecodeTextBase(self, data):
    """Look at a U-Boot image and try to decode its TEXT_BASE.

    This works because U-Boot has a header with the value 0x12345678
    immediately followed by the TEXT_BASE value. We can therefore read this
    from the image with some certainty. We check only the first 40 words
    since the header should be within that region.

    Args:
      data: U-Boot binary data

    Returns:
      Text base (integer) or None if none was found
    """
    found = False
    for i in range(0, 160, 4):
      word = data[i:i + 4]

      # TODO(sjg): This does not cope with a big-endian target
      value = struct.unpack('<I', word)[0]
      if found:
        return value
      if value == 0x12345678:
        found = True

    return None

  def CalcTextBase(self, name, fdt, fname):
    """Calculate the TEXT_BASE to use for U-Boot.

    Normally this value is in the fdt, so we just read it from there. But as
    a second check we look at the image itself in case this is different, and
    switch to that if it is.

    This allows us to flash any U-Boot even if its TEXT_BASE is different.
    This is particularly useful with upstream U-Boot which uses a different
    value (which we will move to).
    """
    data = self._tools.ReadFile(fname)
    fdt_text_base = fdt.GetInt('/chromeos-config', 'textbase')
    text_base = self.DecodeTextBase(data)

    # If they are different, issue a warning and switch over.
    if text_base and text_base != fdt_text_base:
      self._out.Warning("TEXT_BASE %x in %sU-Boot doesn't match "
              "fdt value of %x. Using %x" % (text_base, name,
                  fdt_text_base, text_base))
      fdt_text_base = text_base
    return fdt_text_base

  def _CreateBootStub(self, uboot, base_fdt, postload):
    """Create a boot stub and a signed boot stub.

    For postload:
    We add a /config/postload-text-offset entry to the signed bootstub's
    fdt so that U-Boot can find the postload code.

    The raw (unsigned) bootstub will have a value of -1 for this since we will
    simply append the postload code to the bootstub and it can find it there.
    This will be used for RW A/B firmware.

    For the signed case this value will specify where in the flash to find
    the postload code. This will be used for RO firmware.

    Args:
      uboot: Path to u-boot.bin (may be chroot-relative)
      base_fdt: Fdt object containing the flat device tree.
      postload: Path to u-boot-post.bin, or None if none.

    Returns:
      Tuple containing:
        Full path to bootstub (uboot + fdt(-1) + postload).
        Full path to signed (uboot + fdt(flash pos) + bct) + postload.

    Raises:
      CmdError if a command fails.
    """
    bootstub = os.path.join(self._tools.outdir, 'u-boot-fdt.bin')
    text_base = self.CalcTextBase('', self.fdt, uboot)
    uboot_data = self._tools.ReadFile(uboot)

    # Make a copy of the fdt for the bootstub
    fdt = base_fdt.Copy(os.path.join(self._tools.outdir, 'bootstub.dtb'))
    fdt.PutInteger('/config', 'postload-text-offset', 0xffffffff);
    fdt_data = self._tools.ReadFile(fdt.fname)

    self._tools.WriteFile(bootstub, uboot_data + fdt_data)
    self._tools.OutputSize('U-Boot binary', self.uboot_fname)
    self._tools.OutputSize('U-Boot fdt', self._fdt_fname)
    self._tools.OutputSize('Combined binary', bootstub)

    # Sign the bootstub; this is a combination of the board specific
    # bct and the stub u-boot image.
    signed = self._SignBootstub(self._tools.Filename(self.bct_fname),
        bootstub, text_base)

    signed_postload = os.path.join(self._tools.outdir, 'signed-postload.bin')
    data = self._tools.ReadFile(signed)

    if postload:
      # We must add postload to the bootstub since A and B will need to
      # be able to find it without the /config/postload-text-offset mechanism.
      bs_data = self._tools.ReadFile(bootstub)
      bs_data += self._tools.ReadFile(postload)
      bootstub = os.path.join(self._tools.outdir, 'u-boot-fdt-postload.bin')
      self._tools.WriteFile(bootstub, bs_data)
      self._tools.OutputSize('Combined binary with postload', bootstub)

      # Now that we know the file size, adjust the fdt and re-sign
      postload_bootstub = os.path.join(self._tools.outdir, 'postload.bin')
      fdt.PutInteger('/config', 'postload-text-offset', len(data))
      fdt_data = self._tools.ReadFile(fdt.fname)
      self._tools.WriteFile(postload_bootstub, uboot_data + fdt_data)
      signed = self._SignBootstub(self._tools.Filename(self.bct_fname),
          postload_bootstub, text_base)
      if len(data) != os.path.getsize(signed):
        raise CmdError('Signed file size changed from %d to %d after updating '
            'fdt' % (len(data), os.path.getsize(signed)))

      # Re-read the signed image, and add the post-load binary.
      data = self._tools.ReadFile(signed)
      data += self._tools.ReadFile(postload)
      self._tools.OutputSize('Post-load binary', postload)

    self._tools.WriteFile(signed_postload, data)
    self._tools.OutputSize('Final bootstub with postload', signed_postload)

    return bootstub, signed_postload

  def _CreateCorebootStub(self, uboot, coreboot, fdt, seabios):
    """Create a coreboot boot stub.

    Args:
      uboot: Path to u-boot.bin (may be chroot-relative)
      coreboot: Path to coreboot.rom
      fdt: Device Tree
      seabios: Path to SeaBIOS payload binary or None

    Returns:
      Full path to bootstub (coreboot + uboot + fdt).

    Raises:
      CmdError if a command fails.
    """
    bootstub = os.path.join(self._tools.outdir, 'coreboot-full.rom')
    cbfstool = "/usr/bin/cbfstool"
    uboot_elf = uboot.replace(".bin", ".elf")
    shutil.copyfile(coreboot, bootstub)
    if seabios:
        self._tools.Run(cbfstool, [bootstub, 'add-payload', seabios,
            'fallback/payload', 'lzma'])
        self._tools.Run(cbfstool, [bootstub, 'add-payload', uboot_elf,
            'img/U-Boot', 'lzma'])
    else:
        self._tools.Run(cbfstool, [bootstub, 'add-payload', uboot_elf,
            'fallback/payload', 'lzma'])
    self._tools.Run(cbfstool, [bootstub, 'add', fdt.fname, 'u-boot.dtb',
        '0xac'])
    return bootstub

  def _PackOutput(self, msg):
    """Helper function to write output from PackFirmware (verbose level 2).

    This is passed to PackFirmware for it to use to write output.

    Args:
      msg: Message to display.
    """
    self._out.Notice(msg)

  def _CreateImage(self, gbb, fdt):
    """Create a full firmware image, along with various by-products.

    This uses the provided u-boot.bin, fdt and bct to create a firmware
    image containing all the required parts. If the GBB is not supplied
    then this will just return a signed U-Boot as the image.

    Args:
      gbb:      Full path to the GBB file, or empty if a GBB is not required.
      fdt:      Fdt object containing required information.

    Returns:
      Path to image file

    Raises:
      CmdError if a command fails.
    """
    self._out.Notice("Model: %s" % fdt.GetString('/', 'model'))

    if self.coreboot_fname:
      # FIXME(reinauer) the names are not too great choices.
      # signed gets packed into the bootstub, and bootstub gets
      # packed into the RW sections.
      signed = self._CreateCorebootStub(self.uboot_fname,
          self.coreboot_fname, fdt, self.seabios_fname)
      bootstub = self.uboot_fname
    else:
      # Create the boot stub, which is U-Boot plus an fdt and bct
      bootstub, signed = self._CreateBootStub(self.uboot_fname, fdt,
                                              self.postload_fname)

    if gbb:
      pack = PackFirmware(self._tools, self._out)
      image = os.path.join(self._tools.outdir, 'image.bin')
      fwid = '.'.join([
          re.sub('[ ,]+', '_', fdt.GetString('/', 'model')),
          self._tools.GetChromeosVersion()])
      self._out.Notice('Firmware ID: %s' % fwid)
      pack.SetupFiles(boot=bootstub, signed=signed, gbb=gbb,
          fwid=fwid, keydir=self._keydir)
      pack.SelectFdt(fdt)
      pack.PackImage(self._tools.outdir, image)
    else:
      image = signed

    self._tools.OutputSize('Final image', image)
    return image

  def SelectFdt(self, fdt_fname):
    """Select an FDT to control the firmware bundling

    Args:
      fdt_fname: The filename of the fdt to use.

    Returns:
      The Fdt object of the original fdt file, which we will not modify.

    We make a copy of this which will include any on-the-fly changes we want
    to make.
    """
    self._fdt_fname = fdt_fname
    self.CheckOptions()
    fdt = Fdt(self._tools, self._fdt_fname)
    fdt.Compile()
    self.fdt = fdt.Copy(os.path.join(self._tools.outdir, 'updated.dtb'))
    return fdt

  def Start(self, hardware_id, output_fname):
    """This creates a firmware bundle according to settings provided.

      - Checks options, tools, output directory, fdt.
      - Creates GBB and image.

    Args:
      hardware_id: Hardware ID to use for this board. If None, then the
          default from the Fdt will be used
      output_fname: Output filename for the image. If this is not None, then
          the final image will be copied here.

    Returns:
      Filename of the resulting image (not the output_fname copy).
    """
    gbb = ''
    if not self._small:
      gbb = self._CreateGoogleBinaryBlock(hardware_id)

    # This creates the actual image.
    image = self._CreateImage(gbb, self.fdt)
    if output_fname:
      shutil.copyfile(image, output_fname)
      self._out.Notice("Output image '%s'" % output_fname)
    return image
