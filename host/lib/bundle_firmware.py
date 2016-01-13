# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module builds a firmware image.

This modules uses a few rudimentary other libraries for its activity.

Here are the names we give to the various files we deal with. It is important
to keep these consistent!

  uboot     u-boot.bin (with no device tree)
  fdt       the fdt blob
  bct       the BCT file
  bootstub  uboot + fdt
  signed    (uboot + fdt + bct) signed blob
"""

import glob
import hashlib
import os
import re

from fdt import Fdt
from pack_firmware import PackFirmware
import shutil
import struct
from flashmaps import default_flashmaps
from tools import CmdError
from exynos import ExynosBl2

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

# Build GBB flags.
# (src/platform/vboot_reference/firmware/include/gbb_header.h)
gbb_flag_properties = {
  'dev-screen-short-delay': 0x00000001,
  'load-option-roms': 0x00000002,
  'enable-alternate-os': 0x00000004,
  'force-dev-switch-on': 0x00000008,
  'force-dev-boot-usb': 0x00000010,
  'disable-fw-rollback-check': 0x00000020,
  'enter-triggers-tonorm': 0x00000040,
  'force-dev-boot-legacy': 0x00000080,
  'faft-key-overide': 0x00000100,
  'disable-ec-software-sync': 0x00000200,
  'default-dev-boot-legacy': 0x00000400,
  'disable-pd-software-sync': 0x00000800,
  'force-dev-boot-fastboot-full-cap': 0x00002000,
  'enable-serial': 0x00004000,
}

# Maps board name to Exynos product number
type_to_model = {
  'peach' : '5420',
  'daisy' : '5250'
}

def ListGoogleBinaryBlockFlags():
  """Print out a list of GBB flags."""
  print '   %-30s %s' % ('Available GBB flags:', 'Hex')
  for name, value in gbb_flag_properties.iteritems():
    print '   %-30s %02x' % (name, value)

class BlobDeferral(Exception):
  """An error indicating deferal of blob generation."""
  pass

class Bundle:
  """This class encapsulates the entire bundle firmware logic.

  Sequence of events:
    bundle = Bundle(tools.Tools(), cros_output.Output())
    bundle.SetDirs(...)
    bundle.SetFiles(...)
    bundle.SetOptions(...)
    bundle.SelectFdt(fdt.Fdt('filename.dtb')
    .. can call bundle.AddConfigList(), AddEnableList() if required
    bundle.Start(...)

  Public properties:
    fdt: The fdt object that we use for building our image. This wil be the
        one specified by the user, except that we might add config options
        to it. This is set up by SelectFdt() which must be called before
        bundling starts.
    uboot_fname: Full filename of the U-Boot binary we use.
    bct_fname: Full filename of the BCT file we use.
    spl_source: Source device to load U-Boot from, in SPL:
        straps: Select device according to CPU strap pins
        spi: Boot from SPI
        emmc: Boot from eMMC

  Private attributes:
    _small: True to create a 'small' signed U-Boot, False to produce a
        full image. The small U-Boot is enough to boot but will not have
        access to GBB, RW U-Boot, etc.
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
    self._board = None          # Board name, e.g. nyan.
    self._fdt_fname = None      # Filename of our FDT.
    self._force_rw = None
    self._force_efs = None
    self._gbb_flags = None
    self._keydir = None
    self._small = False
    self.bct_fname = None       # Filename of our BCT file.
    self.blobs = {}             # Table of (type, filename) of arbitrary blobs
    self.bmpblk_fname = None    # Filename of our Bitmap Block
    self.coreboot_elf = None
    self.coreboot_fname = None  # Filename of our coreboot binary.
    self.ecro_fname = None      # Filename of EC read-only file
    self.ecrw_fname = None      # Filename of EC file
    self.pdrw_fname = None      # Filename of PD file
    self.exynos_bl1 = None      # Filename of Exynos BL1 (pre-boot)
    self.exynos_bl2 = None      # Filename of Exynos BL2 (SPL)
    self.fdt = None             # Our Fdt object.
    self.kernel_fname = None
    self.postload_fname = None
    self.seabios_fname = None   # Filename of our SeaBIOS payload.
    self.skeleton_fname = None  # Filename of Coreboot skeleton file
    self.uboot_fname = None     # Filename of our U-Boot binary.

  def SetDirs(self, keydir):
    """Set up directories required for Bundle.

    Args:
      keydir: Directory containing keys to use for signing firmware.
    """
    self._keydir = keydir

  def SetFiles(self, board, bct, uboot=None, bmpblk=None, coreboot=None,
               coreboot_elf=None,
               postload=None, seabios=None, exynos_bl1=None, exynos_bl2=None,
               skeleton=None, ecrw=None, ecro=None, pdrw=None,
               kernel=None, blobs=None, skip_bmpblk=False, cbfs_files=None,
               rocbfs_files=None):
    """Set up files required for Bundle.

    Args:
      board: The name of the board to target (e.g. nyan).
      uboot: The filename of the u-boot.bin image to use.
      bct: The filename of the binary BCT file to use.
      bmpblk: The filename of bitmap block file to use.
      coreboot: The filename of the coreboot image to use (on x86).
      coreboot_elf: If not none, the ELF file to add as a Coreboot payload.
      postload: The filename of the u-boot-post.bin image to use.
      seabios: The filename of the SeaBIOS payload to use if any.
      exynos_bl1: The filename of the exynos BL1 file
      exynos_bl2: The filename of the exynos BL2 file (U-Boot spl)
      skeleton: The filename of the coreboot skeleton file.
      ecrw: The filename of the EC (Embedded Controller) read-write file.
      ecro: The filename of the EC (Embedded Controller) read-only file.
      pdrw: The filename of the PD (PD embedded controller) read-write file.
      kernel: The filename of the kernel file if any.
      blobs: List of (type, filename) of arbitrary blobs.
      skip_bmpblk: True if no bmpblk is required
      cbfs_files: Root directory of files to be stored in RO and RW CBFS
      rocbfs_files: Root directory of files to be stored in RO CBFS
    """
    self._board = board
    self.uboot_fname = uboot
    self.bct_fname = bct
    self.bmpblk_fname = bmpblk
    self.coreboot_fname = coreboot
    self.coreboot_elf = coreboot_elf
    self.postload_fname = postload
    self.seabios_fname = seabios
    self.exynos_bl1 = exynos_bl1
    self.exynos_bl2 = exynos_bl2
    self.skeleton_fname = skeleton
    self.ecrw_fname = ecrw
    self.ecro_fname = ecro
    self.pdrw_fname = pdrw
    self.kernel_fname = kernel
    self.blobs = dict(blobs or ())
    self.skip_bmpblk = skip_bmpblk
    self.cbfs_files = cbfs_files
    self.rocbfs_files = rocbfs_files

  def SetOptions(self, small, gbb_flags, force_rw=False, force_efs=False):
    """Set up options supported by Bundle.

    Args:
      small: Only create a signed U-Boot - don't produce the full packed
          firmware image. This is useful for devs who want to replace just the
          U-Boot part while keeping the keys, gbb, etc. the same.
      gbb_flags: Specification for string containing adjustments to make.
      force_rw: Force firmware into RW mode.
      force_efs: Force firmware to use 'early firmware selection' feature,
          where RW firmware is selected before SDRAM is initialized.
    """
    self._small = small
    self._gbb_flags = gbb_flags
    self._force_rw = force_rw
    self._force_efs = force_efs

  def _GetBuildRoot(self):
    """Get the path to this board's 'firmware' directory.

    Returns:
      Path to firmware directory, with ## representing the path to the
      chroot.
    """
    if not self._board:
      raise ValueError('No board defined - please define a board to use')
    return os.path.join('##', 'build', self._board, 'firmware')

  def _CheckFdtFilename(self, fname):
    """Check provided FDT filename and return the correct name if needed.

    Where the filename lacks a path, add a default path for this board.
    Where no FDT filename is provided, select a default one for this board.

    Args:
      fname: Proposed FDT filename.

    Returns:
      Selected FDT filename, after validation.
    """
    build_root = self._GetBuildRoot()
    dir_name = os.path.join(build_root, 'dtb')
    if not fname:
      # Figure out where the file should be, and the name we expect.
      base_name = re.sub('_', '-', self._board)

      # In case the name exists with a prefix or suffix, find it.
      wildcard = os.path.join(dir_name, '*%s.dtb' % base_name)
      found_list = glob.glob(self._tools.Filename(wildcard))
      if len(found_list) == 1:
        fname = found_list[0]
      else:
        # We didn't find anything definite, so set up our expected name.
        fname = os.path.join(dir_name, '%s.dtb' % base_name)

    # Convert things like 'exynos5250-daisy' into a full path.
    root, ext = os.path.splitext(fname)
    if not ext and not os.path.dirname(root):
      fname = os.path.join(dir_name, '%s.dtb' % root)
    return fname

  def CheckOptions(self):
    """Check provided options and select defaults."""
    build_root = self._GetBuildRoot()

    board_type = self._board.split('_')[0]
    model = type_to_model.get(board_type)

    if not self.uboot_fname:
      self.uboot_fname = os.path.join(build_root, 'u-boot.bin')
    if not self.bct_fname:
      self.bct_fname = os.path.join(build_root, 'bct', 'board.bct')
    if not self.bmpblk_fname:
      self.bmpblk_fname = os.path.join(build_root, 'bmpblk.bin')
    if model:
      if not self.exynos_bl1:
        self.exynos_bl1 = os.path.join(build_root, 'u-boot.bl1.bin')
      if not self.exynos_bl2:
        self.exynos_bl2 = os.path.join(build_root, 'u-boot-spl.wrapped.bin')
    if not self.coreboot_fname:
      self.coreboot_fname = os.path.join(build_root, 'coreboot.rom')
    if not self.skeleton_fname:
      self.skeleton_fname = os.path.join(build_root, 'coreboot.rom')
    if not self.seabios_fname:
      self.seabios_fname = 'seabios.cbfs'
    if not self.ecrw_fname:
      self.ecrw_fname = os.path.join(build_root, 'ec.RW.bin')
    if not self.pdrw_fname:
      self.pdrw_fname = os.path.join(build_root, 'pd.RW.bin')
    if not self.ecro_fname:
      self.ecro_fname = os.path.join(build_root, 'ec.RO.bin')

  def GetFiles(self):
    """Get a list of files that we know about.

    This is the opposite of SetFiles except that we may have put in some
    default names. It returns a dictionary containing the filename for
    each of a number of pre-defined files.

    Returns:
      Dictionary, with one entry for each file.
    """
    file_list = {
        'bct' : self.bct_fname,
        'exynos-bl1' : self.exynos_bl1,
        'exynos-bl2' : self.exynos_bl2,
        }
    return file_list

  def DecodeGBBFlagsFromFdt(self):
    """Get Google Binary Block flags from the FDT.

    These should be in the chromeos-config node, like this:

      chromeos-config {
                  gbb-flag-dev-screen-short-delay;
                  gbb-flag-force-dev-switch-on;
                  gbb-flag-force-dev-boot-usb;
                  gbb-flag-disable-fw-rollback-check;
      };

    Returns:
      GBB flags value from FDT.
    """
    chromeos_config = self.fdt.GetProps("/chromeos-config")
    gbb_flags = 0
    for name in chromeos_config:
      if name.startswith('gbb-flag-'):
        flag_value = gbb_flag_properties.get(name[9:])
        if flag_value:
          gbb_flags |= flag_value
          self._out.Notice("FDT: Enabling %s." % name)
        else:
          raise ValueError("FDT contains invalid GBB flags '%s'" % name)
    return gbb_flags

  def DecodeGBBFlagsFromOptions(self, gbb_flags, adjustments):
    """Decode ajustments to the provided GBB flags.

    We support three options:

       hex value: c2
       defined value: force-dev-boot-usb,load-option-roms
       adjust default value: -load-option-roms,+force-dev-boot-usb

    The last option starts from the passed-in GBB flags and adds or removes
    flags.

    Args:
      gbb_flags: Base (default) FDT flags.
      adjustments: String containing adjustments to make.

    Returns:
      Updated FDT flags.
    """
    use_base_value = True
    if adjustments:
      try:
        return int(adjustments, base=16)
      except (ValueError, TypeError):
        pass
      for flag in adjustments.split(','):
        oper = None
        if flag[0] in ['-', '+']:
          oper = flag[0]
          flag = flag[1:]
        value = gbb_flag_properties.get(flag)
        if not value:
          raise ValueError("Invalid GBB flag '%s'" % flag)
        if oper == '+':
          gbb_flags |= value
          self._out.Notice("Cmdline: Enabling %s." % flag)
        elif oper == '-':
          gbb_flags &= ~value
          self._out.Notice("Cmdline: Disabling %s." % flag)
        else:
          if use_base_value:
            gbb_flags = 0
            use_base_value = False
            self._out.Notice('Cmdline: Resetting flags to 0')
          gbb_flags |= value
          self._out.Notice("Cmdline: Enabling %s." % flag)

    return gbb_flags

  def _CreateGoogleBinaryBlock(self, hardware_id):
    """Create a GBB for the image.

    Args:
      hardware_id: Hardware ID to use for this board. If None, then the
          default from the Fdt will be used

    Returns:
      Path of the created GBB file.
    """
    if not hardware_id:
      hardware_id = self.fdt.GetString('/config', 'hwid')
    gbb_size = self.fdt.GetFlashPartSize('ro', 'gbb')
    odir = self._tools.outdir

    gbb_flags = self.DecodeGBBFlagsFromFdt()

    # Allow command line to override flags
    gbb_flags = self.DecodeGBBFlagsFromOptions(gbb_flags, self._gbb_flags)

    self._out.Notice("GBB flags value %#x" % gbb_flags)
    self._out.Progress('Creating GBB')
    sizes = [0x100, 0x1000, gbb_size - 0x2180, 0x1000]
    sizes = ['%#x' % size for size in sizes]
    gbb = 'gbb.bin'
    keydir = self._tools.Filename(self._keydir)

    gbb_set_command = ['-s',
                       '--hwid=%s' % hardware_id,
                       '--rootkey=%s/root_key.vbpubk' % keydir,
                       '--recoverykey=%s/recovery_key.vbpubk' % keydir,
                       '--flags=%d' % gbb_flags,
                       gbb]
    if not self.skip_bmpblk:
      gbb_set_command[-1:-1] = ['--bmpfv=%s' % self._tools.Filename(
          self.bmpblk_fname),]

    self._tools.Run('gbb_utility', ['-c', ','.join(sizes), gbb], cwd=odir)
    self._tools.Run('gbb_utility', gbb_set_command, cwd=odir)
    return os.path.join(odir, gbb)

  def _SignBootstub(self, bct, bootstub, text_base):
    """Sign an image so that the Tegra SOC will boot it.

    Args:
      bct: BCT file to use.
      bootstub: Boot stub (U-Boot + fdt) file to sign.
      text_base: Address of text base for image.

    Returns:
      filename of signed image.
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
    if bootcmd is not None:
      if bootcmd == 'none':
        bootcmd = ''
      self.fdt.PutString('/config', 'bootcmd', bootcmd)
      self.fdt.PutInteger('/config', 'bootsecure', int(bootsecure))
      self._out.Info('Boot command: %s' % bootcmd)

  def SetNodeEnabled(self, node_name, enabled):
    """Set whether an node is enabled or disabled.

    This simply sets the 'status' property of a node to "ok", or "disabled".

    The node should either be a full path to the node (like '/uart@10200000')
    or an alias property.

    Aliases are supported like this:

        aliases {
                console = "/uart@10200000";
        };

    pointing to a node:

        uart@10200000 {
                status = "okay";
        };

    In this case, this function takes the name of the alias ('console' in
    this case) and updates the status of the node that is pointed to, to
    either ok or disabled. If the alias does not exist, a warning is
    displayed.

    Args:
      node_name: Name of node (e.g. '/uart@10200000') or alias alias
          (e.g. 'console') to adjust
      enabled: True to enable, False to disable
    """
    # Look up the alias if this is an alias reference
    if not node_name.startswith('/'):
      lookup = self.fdt.GetString('/aliases', node_name, '')
      if not lookup:
        self._out.Warning("Cannot find alias '%s' - ignoring" % node_name)
        return
      node_name = lookup
    if enabled:
      status = 'okay'
    else:
      status = 'disabled'
    self.fdt.PutString(node_name, 'status', status)

  def AddEnableList(self, enable_list):
    """Process a list of nodes to enable/disable.

    Args:
      enable_list: List of (node, value) tuples to add to the fdt. For each
          tuple:
              node: The fdt node to write to will be <node> or pointed to by
                  /aliases/<node>. We can tell which
              value: 0 to disable the node, 1 to enable it

    Raises:
      CmdError if a command fails.
    """
    if enable_list:
      for node_name, enabled in enable_list:
        try:
          enabled = int(enabled)
          if enabled not in (0, 1):
            raise ValueError
        except ValueError:
          raise CmdError("Invalid enable option value '%s' "
              "(should be 0 or 1)" % str(enabled))
        self.SetNodeEnabled(node_name, enabled)

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
          except ValueError:
            raise CmdError("Cannot convert config option '%s' to integer" %
                str(value))
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

    Since upstream Tegra has moved to having a 16KB SPL region at the start,
    and currently this does holds the U-Boot text base (e.g. 0x10c000) instead
    of the SPL one (e.g. 0x108000), we search in the U-Boot part as well.

    Args:
      data: U-Boot binary data

    Returns:
      Text base (integer) or None if none was found
    """
    found = False
    for start in (0, 0x4000):
      for i in range(start, start + 160, 4):
        word = data[i:i + 4]

        # TODO(sjg): This does not cope with a big-endian target
        value = struct.unpack('<I', word)[0]
        if found:
          return value - start
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
    # The value that comes back from fdt.GetInt is signed, which makes no
    # sense for an address base.  Force it to unsigned.
    fdt_text_base = fdt.GetInt('/chromeos-config', 'textbase', 0) & 0xffffffff
    text_base = self.DecodeTextBase(data)
    text_base_str = '%#x' % text_base if text_base else 'None'
    self._out.Info('TEXT_BASE: fdt says %#x, %s says %s' % (fdt_text_base,
        fname, text_base_str))

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
    fdt.PutInteger('/config', 'postload-text-offset', 0xffffffff)
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

  def _AddCbfsFiles(self, bootstub, cbfs_files):
    for dir, subs, files in os.walk(cbfs_files):
      for file in files:
        file = os.path.join(dir, file)
        cbfs_name = file.replace(cbfs_files, '', 1).strip('/')
        self._tools.Run('cbfstool', [bootstub, 'add', '-f', file,
                                '-n', cbfs_name, '-t', 'raw', '-c', 'lzma'])

  def _ProcessCbfsFileProperty(self, cb_copy, node):
    """Add files to CBFS in RW regions using a specification in fmap.dts

    rw-a-boot {
      ...
      cbfs-files {
       ecfoo = "add -n ecrw-copy -f ec.RW.bin -t raw -A sha256";
      };
    };

    Adds a file called "ecrw-copy" of raw type to FW_MAIN_A with the
    content of ec.RW.bin in the build root, with a SHA256 hash.
    The dts property name ("ecfoo") is ignored but should be unique,
    all cbfstool commands that start with "add" are allowed, as is "remove".
    The second and third argument need to be "-n <cbfs file name>".
    """
    try:
      cbfs_config = self.fdt.GetProps(node + '/cbfs-files')
    except CmdError:
      cbfs_config = None

    # Ignore first character of node string,
    # so both /flash/foo and flash/foo work.
    region = node[1:].split('/')[1]
    part_sections = region.split('-', 1)
    fmap_dst = self._FmapNameByPath(part_sections)

    if cbfs_config != None:
      # remove all files slated for addition, in case they already exist
      for val in cbfs_config.itervalues():
        f = val.split(' ')
        command = f[0]
        if command[:3] != 'add' and command != 'remove':
          raise CmdError("'%s' doesn't add or remove a file", f)
        if f[1] != '-n':
          raise CmdError("second argument in '%s' must be '-n'", f)
        cbfsname = f[2]
        try:
          # Calling through shell isn't strictly necessary here, but we still
          # do it to keep operation more similar to the invocation in the next
          # loop.
          self._tools.Run('sh', [ '-c',
            ' '.join(['cbfstool', cb_copy, 'remove', '-r', fmap_dst,
                                       '-n', cbfsname]) ])
        except CmdError:
          pass # the most likely error is that the file doesn't already exist

      # now add the files
      for val in cbfs_config.itervalues():
        f = val.split(' ')
        command = f[0]
        cbfsname = f[2]
        args = f[3:]
        if command == 'remove':
          continue
        # Call through shell so variable expansion can happen. With a change
        # to the ebuild this enables specifying filename arguments to
        # cbfstool as -f romstage.elf${COREBOOT_VARIANT} and have that be
        # resolved to romstage.elf.serial when appropriate.
        self._tools.Run('sh', [ '-c',
            ' '.join(['cbfstool', cb_copy, command, '-r', fmap_dst,
                      '-n', cbfsname] + args)],
                      self._tools.Filename(self._GetBuildRoot()))

  def _CreateCorebootStub(self, pack, coreboot):
    """Create a coreboot boot stub and add pack properties.

    Args:
      pack: a PackFirmware object describing the firmware image to build.
      coreboot: Path to coreboot.rom
    """
    bootstub = os.path.join(self._tools.outdir, 'coreboot-full.rom')
    shutil.copyfile(self._tools.Filename(coreboot), bootstub)

    pack.AddProperty('coreboot', bootstub)
    pack.AddProperty('image', bootstub)

    # Add files to to RO and RW CBFS if provided.
    if self.cbfs_files:
      self._AddCbfsFiles(bootstub, self.cbfs_files)

    # Create a coreboot copy to use as a scratch pad. Order matters. The
    # cbfs_files were added prior to this action. That's so the RW CBFS
    # regions inherit the files from the RO CBFS region. Additionally,
    # include the full FMAP within the file.
    cb_copy = os.path.abspath(os.path.join(self._tools.outdir, 'cb_with_fmap'))
    self._tools.WriteFile(cb_copy, self._tools.ReadFile(bootstub))
    binary = self._tools.ReadFile(bootstub)
    fmap_offset, fmap = pack.GetFmap()
    if len(binary) < fmap_offset + len(fmap):
        raise CmdError('FMAP will not fit')
    # Splice in FMAP data.
    binary = binary[:fmap_offset] + fmap + binary[fmap_offset + len(fmap):]
    self._tools.WriteFile(cb_copy, binary)
    # Publish where coreboot is with the FMAP data.
    pack.AddProperty('cb_with_fmap', cb_copy)

    # Add files to to RO CBFS if provided. This done here such that the
    # copy above does not contain the RO CBFS files.
    if self.rocbfs_files:
      self._AddCbfsFiles(bootstub, self.rocbfs_files)

    # As a final step, do whatever is requested in /flash/ro-boot/cbfs-files.
    # It's done after creating the copy for the RW regions so that ro-boot's
    # cbfs-files property has no side-effects on the RW regions.
    node = self.fdt.GetFlashNode('ro', 'boot')
    self._ProcessCbfsFileProperty(os.path.abspath(bootstub), node)


  def _PackOutput(self, msg):
    """Helper function to write output from PackFirmware (verbose level 2).

    This is passed to PackFirmware for it to use to write output.

    Args:
      msg: Message to display.
    """
    self._out.Notice(msg)

  def _FmapNameByPath(self, path):
    """ Take list of names to form node path. Return FMAP name.

    Obtain the FMAP name described by the node path.

    Args:
      path: list forming a node path.

    Returns:
      FMAP name of fdt node.

    Raises:
      CmdError if path not found.
    """
    lbl = self.fdt.GetLabel(self.fdt.GetFlashNode(*path))
    return re.sub('-', '_', lbl).upper()

  def _PrepareCbfsHash(self, pack, blob_name):
    """Create blob in rw-{a,b}-boothash with 'cbfstool hashcbfs'.

    When the blob name is defined as cbfshash/<section>/<subsection>, fill the
    <section>_<subsection> area in the flash map with CBFS hash generated
    using the 'cbfstool hashcbfs' command.

    Args:
      pack: a PackFirmware object describing the firmware image to build.
      blob_name: a string, blob name describing what FMAP section this CBFS
                 copy is destined to
    Raises:
      CmdError if cbfs-files node has incorrect parameters.
      BlobDeferral if the CBFS region is not populated yet or if the coreboot
      image with fmap is not available yet.
    """
    cb_copy = pack.GetProperty('cb_with_fmap')
    if cb_copy is None:
      raise BlobDeferral("Waiting for '%s'" % cb_copy)

    part_sections = blob_name.split('/')[1:]
    fmap_dst = self._FmapNameByPath(part_sections)

    # Example of FDT ndoes asking for CBFS hash:
    #  rw-b-boot {
    #          label = "fw-main-b";
    #          reg = <0x00700000 0x002dff80>;
    #          type = "blob cbfs/rw/b-boot";
    #  };
    #  rw-b-boothash {
    #          label = "fw-main-b-hash";
    #          reg = <0x009dff80 0x00000040>;
    #          type = "blob cbfshash/rw/b-boothash";
    #          cbfs-node = "cbfs/rw/b-boot";
    #  };
    hash_node = self.fdt.GetFlashNode(*part_sections)
    cbfs_blob_name =  self.fdt.GetString(hash_node, 'cbfs-node')

    if not pack.GetProperty(cbfs_blob_name):
      raise BlobDeferral("Waiting for '%s'" % cbfs_blob_name)

    cbfs_node_path = cbfs_blob_name.split('/')[1:]
    fmap_src = self._FmapNameByPath(cbfs_node_path)

    # Compute CBFS hash and place it in the corect spot.
    self._tools.Run('cbfstool', [cb_copy, 'hashcbfs', '-r', fmap_dst,
                                 '-R', fmap_src, '-A', 'sha256'])

    # Base address and size of the desitnation partition
    base, size = self.fdt.GetFlashPart(*part_sections)

    # And extract the blob for the FW section
    rw_section = os.path.join(self._tools.outdir, '_'.join(part_sections))
    self._tools.WriteFile(rw_section,
                          self._tools.ReadFile(cb_copy)[base:base+size])

    pack.AddProperty(blob_name, rw_section)


  def _PrepareCbfs(self, pack, blob_name):
    """Create CBFS blob in rw-boot-{a,b} FMAP sections.

    When the blob name is defined as cbfs#<section>#<subsection>, fill the
    <section>_<subsection> area in the flash map with a CBFS copy, putting the
    CBFS header of the copy at the base of the section.

    If --coreboot-elf parameter was specified during cros_bumdle_firmware
    invocation, add the parameter of this option as the payload to the new
    CBFS instance.

    Args:
      pack: a PackFirmware object describing the firmware image to build.
      blob_name: a string, blob name describing what FMAP section this CBFS
                 copy is destined to
    Raises:
      CmdError if cbfs-files node has incorrect parameters.
      BlobDeferral if coreboot image with fmap is not available yet.
    """
    cb_copy = pack.GetProperty('cb_with_fmap')
    if cb_copy is None:
      raise BlobDeferral("Waiting for 'cb_with_fmap' property")

    part_sections = blob_name.split('/')[1:]
    fmap_src = self._FmapNameByPath('ro-boot'.split('-'))
    fmap_dst = self._FmapNameByPath(part_sections)

    # Base address and size of the desitnation partition
    base, size = self.fdt.GetFlashPart(*part_sections)

    # Copy CBFS to the required offset
    self._tools.Run('cbfstool', [cb_copy, 'copy', '-r', fmap_dst,
                                 '-R', fmap_src])

    # Add a CBFS master header for good measure
    self._tools.Run('cbfstool', [cb_copy, 'add-master-header',
                                 '-r', fmap_dst])

    # Add coreboot payload if so requested. Note that the some images use
    # different payload for the rw sections, which is passed in as the value
    # of the --uboot option in the command line.
    if self.uboot_fname:
      payload_fname = self.uboot_fname
    elif self.coreboot_elf:
      payload_fname = self.coreboot_elf
    else:
      payload_fname = None

    if payload_fname:
      self._tools.Run('cbfstool', [
        cb_copy, 'add-payload', '-f', payload_fname,
        '-n', 'fallback/payload', '-c', 'lzma' , '-r', fmap_dst])

    if self.ecrw_fname:
      self._tools.Run('cbfstool', [
        cb_copy, 'add', '-f', self.ecrw_fname, '-t', 'raw',
        '-n', 'ecrw', '-A', 'sha256', '-r', fmap_dst ])

    if self.pdrw_fname:
      self._tools.Run('cbfstool', [
        cb_copy, 'add', '-f', self.pdrw_fname, '-t', 'raw',
        '-n', 'pdrw', '-A', 'sha256', '-r', fmap_dst ])

    # Check if there's an advanced CBFS configuration request
    node = self.fdt.GetFlashNode(*part_sections)
    self._ProcessCbfsFileProperty(cb_copy, node)

    # And extract the blob for the FW section
    rw_section = os.path.join(self._tools.outdir, '_'.join(part_sections))
    self._tools.WriteFile(rw_section,
                          self._tools.ReadFile(cb_copy)[base:base+size])

    pack.AddProperty(blob_name, rw_section)


  def _BuildBlob(self, pack, fdt, blob_type):
    """Build the blob data for a particular blob type.

    Args:
      pack: a PackFirmware object describing the firmware image to build.
      fdt: an fdt object including image layout information
      blob_type: The type of blob to create data for. Supported types are:
          coreboot    A coreboot image (ROM plus U-boot and .dtb payloads).
          signed      Nvidia T20/T30 signed image (BCT, U-Boot, .dtb).

    Raises:
      CmdError if a command fails.
      BlobDeferral if a blob is waiting for a dependency.
    """
    # stupid pylint insists that sha256 is not in hashlib.
    # pylint: disable=E1101
    if blob_type == 'coreboot':
      self._CreateCorebootStub(pack, self.coreboot_fname)
    elif blob_type == 'legacy':
      pack.AddProperty('legacy', self.seabios_fname)
    elif blob_type == 'signed':
      bootstub, signed = self._CreateBootStub(self.uboot_fname, fdt,
                                              self.postload_fname)
      pack.AddProperty('bootstub', bootstub)
      pack.AddProperty('signed', signed)
      pack.AddProperty('image', signed)
    elif blob_type == 'exynos-bl1':
      pack.AddProperty(blob_type, self.exynos_bl1)

    # TODO(sjg@chromium.org): Deprecate ecbin
    elif blob_type in ['ecrw', 'ecbin']:
      pack.AddProperty('ecrw', self.ecrw_fname)
      pack.AddProperty('ecbin', self.ecrw_fname)
    elif blob_type == 'pdrw':
      pack.AddProperty('pdrw', self.pdrw_fname)
    elif blob_type == 'ecrwhash':
      ec_hash_file = os.path.join(self._tools.outdir, 'ec_hash.bin')
      ecrw = self._tools.ReadFile(self.ecrw_fname)
      hasher = hashlib.sha256()
      hasher.update(ecrw)
      self._tools.WriteFile(ec_hash_file, hasher.digest())
      pack.AddProperty(blob_type, ec_hash_file)
    elif blob_type == 'pdrwhash':
      pd_hash_file = os.path.join(self._tools.outdir, 'pd_hash.bin')
      pdrw = self._tools.ReadFile(self.pdrw_fname)
      hasher = hashlib.sha256()
      hasher.update(pdrw)
      self._tools.WriteFile(pd_hash_file, hasher.digest())
      pack.AddProperty(blob_type, pd_hash_file)
    elif blob_type == 'ecro':
      # crosbug.com/p/13143
      # We cannot have an fmap in the EC image since there can be only one,
      # which is the main fmap describing the whole image.
      # Ultimately the EC will not have an fmap, since with software sync
      # there is no flashrom involvement in updating the EC flash, and thus
      # no need for the fmap.
      # For now, mangle the fmap name to avoid problems.
      updated_ecro = os.path.join(self._tools.outdir, 'updated-ecro.bin')
      data = self._tools.ReadFile(self.ecro_fname)
      data = re.sub('__FMAP__', '__fMAP__', data)
      self._tools.WriteFile(updated_ecro, data)
      pack.AddProperty(blob_type, updated_ecro)
    elif blob_type.startswith('exynos-bl2'):
      # We need to configure this per node, so do it later
      pass
    elif blob_type.startswith('cbfshash'):
      self._PrepareCbfsHash(pack, blob_type)
    elif blob_type.startswith('cbfs'):
      self._PrepareCbfs(pack, blob_type)
    elif pack.GetProperty(blob_type):
      pass
    elif blob_type in self.blobs:
      pack.AddProperty(blob_type, self.blobs[blob_type])
    else:
      raise CmdError("Unknown blob type '%s' required in flash map" %
          blob_type)

  def _BuildBlobs(self, pack, fdt):
    """Build the blob data for the list of blobs in the pack.

    Args:
      pack: a PackFirmware object describing the firmware image to build.
      fdt: an fdt object including image layout information

    Raises:
      CmdError if a command fails.
      BlobDeferral if dependencies cannot be met because of cycles.
    """
    blob_list = pack.GetBlobList()
    self._out.Info('Building blobs %s\n' % blob_list)

    complete = False
    deferred_list = []

    # Build blobs allowing for dependencies between blobs. While this is
    # an potential O(n^2) operation, in practice most blobs aren't dependent
    # and should resolve in a few passes.
    while not complete:
      orig = set(blob_list)
      for blob_type in blob_list:
        try:
          self._BuildBlob(pack, fdt, blob_type)
        except (BlobDeferral):
          deferred_list.append(blob_type)
      if not deferred_list:
        complete = True
      # If deferred is the same as the original no progress is being made.
      if not orig - set(deferred_list):
        raise BlobDeferral("Blob cyle '%s'" % orig)
      # Process the deferred blobs
      blob_list = deferred_list[:]
      deferred_list = []

  def _CreateImage(self, gbb, fdt):
    """Create a full firmware image, along with various by-products.

    This uses the provided u-boot.bin, fdt and bct to create a firmware
    image containing all the required parts. If the GBB is not supplied
    then this will just return a signed U-Boot as the image.

    Args:
      gbb: a string, full path to the GBB file, or empty if a GBB is not
           required.
      fdt: an fdt object containing required information.

    Returns:
      Path to image file
    """
    self._out.Notice("Model: %s" % fdt.GetString('/', 'model'))

    pack = PackFirmware(self._tools, self._out)
    if self._force_rw:
      fdt.PutInteger('/flash/rw-a-vblock', 'preamble-flags', 0)
      fdt.PutInteger('/flash/rw-b-vblock', 'preamble-flags', 0)
    if self._force_efs:
      fdt.PutInteger('/chromeos-config', 'early-firmware-selection', 1)
    pack.use_efs = fdt.GetInt('/chromeos-config', 'early-firmware-selection',
                              0)

    pack.SelectFdt(fdt, self._board)

    # Get all our blobs ready
    if self.uboot_fname:
      pack.AddProperty('boot', self.uboot_fname)
    if self.skeleton_fname:
      pack.AddProperty('skeleton', self.skeleton_fname)
    pack.AddProperty('dtb', fdt.fname)

    # If we are writing a kernel, add its offset from TEXT_BASE to the fdt.
    if self.kernel_fname:
      fdt.PutInteger('/config', 'kernel-offset', pack.image_size)

    if gbb:
      pack.AddProperty('gbb', gbb)

    # Build the blobs out.
    self._BuildBlobs(pack, fdt)

    self._out.Progress('Packing image')
    if gbb:
      pack.RequireAllEntries()
      fwid = '.'.join([
          re.sub('[ ,]+', '_', fdt.GetString('/', 'model')),
          self._tools.GetChromeosVersion()])
      self._out.Notice('Firmware ID: %s' % fwid)
      pack.AddProperty('fwid', fwid)
      pack.AddProperty('keydir', self._keydir)

    # Some blobs need to be configured according to the node they are in.
    todo = pack.GetMissingBlobs()
    for blob in todo:
      if blob.key.startswith('exynos-bl2'):
        bl2 = ExynosBl2(self._tools, self._out)
        pack.AddProperty(blob.key, bl2.MakeSpl(pack, fdt, blob,
                         self.exynos_bl2))

    pack.CheckProperties()

    # Record position and size of all blob members in the FDT
    pack.UpdateBlobPositionsAndHashes(fdt)

    # Recalculate the Exynos BL2, since it may have a hash. The call to
    # UpdateBlobPositionsAndHashes() may have updated the hash-target so we
    # need to recalculate the hash.
    for blob in todo:
      if blob.key.startswith('exynos-bl2'):
        bl2 = ExynosBl2(self._tools, self._out)
        pack.AddProperty(blob.key, bl2.MakeSpl(pack, fdt, blob,
                                               self.exynos_bl2))

    # Make a copy of the fdt for the bootstub
    fdt_data = self._tools.ReadFile(fdt.fname)
    if self.uboot_fname:
      uboot_data = self._tools.ReadFile(self.uboot_fname)
      uboot_copy = os.path.join(self._tools.outdir, 'u-boot.bin')
      self._tools.WriteFile(uboot_copy, uboot_data)

      uboot_dtb = os.path.join(self._tools.outdir, 'u-boot-dtb.bin')
      self._tools.WriteFile(uboot_dtb, uboot_data + fdt_data)

    # Fix up the coreboot image here, since we can't do this until we have
    # a final device tree binary.
    if 'coreboot' in pack.GetBlobList():
      bootstub = pack.GetProperty('coreboot')
      fdt = fdt.Copy(os.path.join(self._tools.outdir, 'bootstub.dtb'))
      if self.coreboot_elf:
        self._tools.Run('cbfstool', [bootstub, 'add-payload', '-f',
            self.coreboot_elf, '-n', 'fallback/payload', '-c', 'lzma'])
      elif self.uboot_fname:
        text_base = 0x1110000

        # This is the the 'movw $GD_FLG_COLD_BOOT, %bx' instruction
        # 1110015:       66 bb 00 01             mov    $0x100,%bx
        marker = struct.pack('<L', 0x0100bb66)
        pos = uboot_data.find(marker)
        if pos == -1 or pos > 0x100:
          raise ValueError('Cannot find U-Boot cold boot entry point')
        entry = text_base + pos
        self._out.Notice('U-Boot entry point %#08x' % entry)
        self._tools.Run('cbfstool', [bootstub, 'add-flat-binary', '-f',
            uboot_dtb, '-n', 'fallback/payload', '-c', 'lzma',
            '-l', '%#x' % text_base, '-e', '%#x' % entry])
      self._tools.Run('cbfstool', [bootstub, 'add', '-f', fdt.fname,
          '-n', 'u-boot.dtb', '-t', '0xac'])
      data = self._tools.ReadFile(bootstub)
      bootstub_copy = os.path.join(self._tools.outdir, 'coreboot-8mb.rom')
      self._tools.WriteFile(bootstub_copy, data)

      # Use offset and size from fmap.dts to extract CBFS area from coreboot.rom
      cbfs_offset, cbfs_size = fdt.GetFlashPart('ro', 'boot')
      self._tools.WriteFile(bootstub, data[cbfs_offset:cbfs_offset+cbfs_size])

    pack.AddProperty('fdtmap', fdt.fname)
    image = os.path.join(self._tools.outdir, 'image.bin')
    pack.PackImage(self._tools.outdir, image)
    pack.AddProperty('image', image)

    image = pack.GetProperty('image')
    self._tools.OutputSize('Final image', image)
    return image, pack

  def SelectFdt(self, fdt_fname, use_defaults):
    """Select an FDT to control the firmware bundling

    We make a copy of this which will include any on-the-fly changes we want
    to make.

    Args:
      fdt_fname: The filename of the fdt to use.
      use_defaults: True to use a default FDT name if available, and to add
          a full path to the provided filename if necessary.

    Returns:
      The Fdt object of the original fdt file, which we will not modify.

    Raises:
      ValueError if no FDT is provided (fdt_fname is None and use_defaults is
          False).
    """
    if use_defaults:
      fdt_fname = self._CheckFdtFilename(fdt_fname)
    if not fdt_fname:
      raise ValueError('Please provide an FDT filename')
    fdt = Fdt(self._tools, fdt_fname)
    self._fdt_fname = fdt_fname

    # For upstream, select the correct architecture .dtsi manually.
    if self._board == 'link' or 'x86' in self._board:
      arch_dts = 'coreboot.dtsi'
    elif self._board == 'daisy':
      arch_dts = 'exynos5250.dtsi'
    else:
      arch_dts = 'tegra124.dtsi'

    fdt.Compile(arch_dts)
    fdt = fdt.Copy(os.path.join(self._tools.outdir, 'updated.dtb'))

    # Get the flashmap so we know what to build. For board variants use the
    # main board name as the key (drop the _<variant> suffix).
    default_flashmap = default_flashmaps.get(self._board.split('_')[0], [])

    if not fdt.GetProp('/flash', 'reg', ''):
      fdt.InsertNodes(default_flashmap)

    # Only check for /iram and /config nodes for boards that require it.
    if self._board in ('daisy', 'peach'):
      # Insert default values for any essential properties that are missing.
      # This should only happen for upstream U-Boot, until our changes are
      # upstreamed.
      if not fdt.GetProp('/iram', 'reg', ''):
        self._out.Warning('Cannot find /iram, using default')
        fdt.InsertNodes([i for i in default_flashmap if i['path'] == '/iram'])

      # Sadly the pit branch has an invalid /memory node. Work around it
      # for now. crosbug.com/p/22184
      if (not fdt.GetProp('/memory', 'reg', '') or
          fdt.GetIntList('/memory', 'reg')[0] == 0):
        self._out.Warning('Cannot find /memory, using default')
        fdt.InsertNodes([i for i in default_flashmap if i['path'] == '/memory'])

      if not fdt.GetProp('/config', 'samsung,bl1-offset', ''):
        self._out.Warning('Missing properties in /config, using defaults')
        fdt.InsertNodes([i for i in default_flashmap if i['path'] == '/config'])

    # Remember our board type.
    fdt.PutString('/chromeos-config', 'board', self._board)

    self.fdt = fdt
    return fdt

  def Start(self, hardware_id, output_fname, show_map):
    """This creates a firmware bundle according to settings provided.

      - Checks options, tools, output directory, fdt.
      - Creates GBB and image.

    Args:
      hardware_id: Hardware ID to use for this board. If None, then the
          default from the Fdt will be used
      output_fname: Output filename for the image. If this is not None, then
          the final image will be copied here.
      show_map: Show a flash map, with each area's name and position

    Returns:
      Filename of the resulting image (not the output_fname copy).
    """
    if self._small or self.fdt.GetProp('/config', 'nogbb', 'any') != 'any':
      gbb = ''  # Building a small image or `nogbb' is requested in device tree.
    else:
      gbb = self._CreateGoogleBinaryBlock(hardware_id)

    # This creates the actual image.
    image, pack = self._CreateImage(gbb, self.fdt)
    if show_map:
      pack.ShowMap()
    if output_fname:
      shutil.copyfile(image, output_fname)
      self._out.Notice("Output image '%s'" % output_fname)
    return image, pack.props
