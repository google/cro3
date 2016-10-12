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
import os
import re

from fdt import Fdt
from pack_firmware import PackFirmware
import shutil
import struct
import fmap
from tools import CmdError

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
    self._force_efs = None
    self._gbb_flags = None
    self._keydir = None
    self._small = False
    self.bct_fname = None       # Filename of our BCT file.
    self.blobs = {}             # Table of (type, filename) of arbitrary blobs
    self.coreboot_elf = None
    self.coreboot_fname = None  # Filename of our coreboot binary.
    self.ecro_fname = None      # Filename of EC read-only file
    self.ecrw_fname = None      # Filename of EC file
    self.pdrw_fname = None      # Filename of PD file
    self.exynos_bl1 = None      # Filename of Exynos BL1 (pre-boot)
    self.exynos_bl2 = None      # Filename of Exynos BL2 (SPL)
    self.fdt = None             # Our Fdt object.
    self.kernel_fname = None
    self.seabios_fname = None   # Filename of our SeaBIOS payload.
    self.skeleton_fname = None  # Filename of Coreboot skeleton file
    self.uboot_fname = None     # Filename of our U-Boot binary.
    self.hardware_id = None
    self.bootstub = None
    self.cb_copy = None
    self.fwid = None

  def SetDirs(self, keydir):
    """Set up directories required for Bundle.

    Args:
      keydir: Directory containing keys to use for signing firmware.
    """
    self._keydir = keydir

  def SetFiles(self, board, bct, uboot=None, coreboot=None,
               coreboot_elf=None,
               seabios=None, exynos_bl1=None, exynos_bl2=None,
               skeleton=None, ecrw=None, ecro=None, pdrw=None,
               kernel=None, blobs=None, cbfs_files=None,
               rocbfs_files=None):
    """Set up files required for Bundle.

    Args:
      board: The name of the board to target (e.g. nyan).
      uboot: The filename of the u-boot.bin image to use.
      bct: The filename of the binary BCT file to use.
      coreboot: The filename of the coreboot image to use (on x86).
      coreboot_elf: If not none, the ELF file to add as a Coreboot payload.
      seabios: The filename of the SeaBIOS payload to use if any.
      exynos_bl1: The filename of the exynos BL1 file
      exynos_bl2: The filename of the exynos BL2 file (U-Boot spl)
      skeleton: The filename of the coreboot skeleton file.
      ecrw: The filename of the EC (Embedded Controller) read-write file.
      ecro: The filename of the EC (Embedded Controller) read-only file.
      pdrw: The filename of the PD (PD embedded controller) read-write file.
      kernel: The filename of the kernel file if any.
      blobs: List of (type, filename) of arbitrary blobs.
      cbfs_files: Root directory of files to be stored in RO and RW CBFS
      rocbfs_files: Root directory of files to be stored in RO CBFS
    """
    self._board = board
    self.uboot_fname = uboot
    self.bct_fname = bct
    self.coreboot_fname = coreboot
    self.coreboot_elf = coreboot_elf
    self.seabios_fname = seabios
    self.exynos_bl1 = exynos_bl1
    self.exynos_bl2 = exynos_bl2
    self.skeleton_fname = skeleton
    self.ecrw_fname = ecrw
    self.ecro_fname = ecro
    self.pdrw_fname = pdrw
    self.kernel_fname = kernel
    self.blobs = dict(blobs or ())
    self.cbfs_files = cbfs_files
    self.rocbfs_files = rocbfs_files

  def SetOptions(self, small, gbb_flags, force_efs=False):
    """Set up options supported by Bundle.

    Args:
      small: Only create a signed U-Boot - don't produce the full packed
          firmware image. This is useful for devs who want to replace just the
          U-Boot part while keeping the keys, gbb, etc. the same.
      gbb_flags: Specification for string containing adjustments to make.
      force_efs: Force firmware to use 'early firmware selection' feature,
          where RW firmware is selected before SDRAM is initialized.
    """
    self._small = small
    self._gbb_flags = gbb_flags
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
    if model:
      if not self.exynos_bl1:
        self.exynos_bl1 = os.path.join(build_root, 'u-boot.bl1.bin')
      if not self.exynos_bl2:
        self.exynos_bl2 = os.path.join(build_root, 'u-boot-spl.wrapped.bin')
    if not self.coreboot_fname:
      self.coreboot_fname = os.path.join(build_root, 'coreboot.rom')
    if not self.skeleton_fname:
      self.skeleton_fname = os.path.join(build_root, 'coreboot.rom')
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

  def _CreateGoogleBinaryBlock(self):
    """Create a GBB for the image.

    Args:
      hardware_id: Hardware ID to use for this board. If None, then the
          default from the Fdt will be used

    Returns:
      Path of the created GBB file.
    """
    hardware_id = self.hardware_id
    if not hardware_id:
      hardware_id = self.fdt.GetString('/config', 'hwid')
    odir = self._tools.outdir

    gbb_flags = self.DecodeGBBFlagsFromFdt()

    # Allow command line to override flags
    gbb_flags = self.DecodeGBBFlagsFromOptions(gbb_flags, self._gbb_flags)

    self._out.Notice("GBB flags value %#x" % gbb_flags)
    self._out.Progress('Creating GBB')
    sizes = [0x100, 0x1000, 0, 0x1000]
    sizes = ['%#x' % size for size in sizes]
    gbb = 'gbb.bin'
    keydir = self._tools.Filename(self._keydir)

    gbb_set_command = ['-s',
                       '--hwid=%s' % hardware_id,
                       '--rootkey=%s/root_key.vbpubk' % keydir,
                       '--recoverykey=%s/recovery_key.vbpubk' % keydir,
                       '--flags=%d' % gbb_flags,
                       gbb]

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

  def _AddCbfsFiles(self, bootstub, cbfs_files, regions='COREBOOT'):
    for dir, subs, files in os.walk(cbfs_files):
      for file in files:
        file = os.path.join(dir, file)
        cbfs_name = file.replace(cbfs_files, '', 1).strip('/')
        self._tools.Run('cbfstool', [bootstub, 'add', '-f', file,
                                '-n', cbfs_name, '-t', 'raw', '-c', 'lzma',
                                '-r', regions])

  def _CreateCorebootStub(self, coreboot):
    """Create a coreboot boot stub.

    Args:
      coreboot: Path to coreboot.rom
    """
    bootstub = os.path.join(self._tools.outdir, 'coreboot-full.rom')
    shutil.copyfile(self._tools.Filename(coreboot), bootstub)

    self.bootstub = bootstub

    # Add files to to RO and RW CBFS if provided.
    if self.cbfs_files:
      self._AddCbfsFiles(bootstub, self.cbfs_files,
          'COREBOOT,FW_MAIN_A,FW_MAIN_B')

    # Add files to to RO CBFS if provided.
    if self.rocbfs_files:
      self._AddCbfsFiles(bootstub, self.rocbfs_files)

    # Create a coreboot copy to use as a scratch pad.
    cb_copy = os.path.abspath(os.path.join(self._tools.outdir, 'cb_with_fmap'))
    self._tools.WriteFile(cb_copy, self._tools.ReadFile(bootstub))
    binary = self._tools.ReadFile(bootstub)
    self._tools.WriteFile(cb_copy, binary)
    self.cb_copy = cb_copy

  def _PackOutput(self, msg):
    """Helper function to write output from PackFirmware (verbose level 2).

    This is passed to PackFirmware for it to use to write output.

    Args:
      msg: Message to display.
    """
    self._out.Notice(msg)

  def _FdtNameToFmap(self, fdtstr):
    return re.sub('-', '_', fdtstr).upper()

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
    return self._FdtNameToFmap(lbl)

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
    """
    part_sections = blob_name.split('/')[1:]
    fmap_dst = self._FmapNameByPath(part_sections)

    # Base address and size of the desitnation partition
    base, size = self.fdt.GetFlashPart(*part_sections)

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
        self.cb_copy, 'add-payload', '-f', payload_fname,
        '-n', 'fallback/payload', '-c', 'lzma' , '-r', fmap_dst])

    if self.ecrw_fname:
      self._tools.Run('cbfstool', [
        self.cb_copy, 'add', '-f', self.ecrw_fname, '-t', 'raw',
        '-n', 'ecrw', '-A', 'sha256', '-r', fmap_dst ])

    if self.pdrw_fname:
      self._tools.Run('cbfstool', [
        self.cb_copy, 'add', '-f', self.pdrw_fname, '-t', 'raw',
        '-n', 'pdrw', '-A', 'sha256', '-r', fmap_dst ])

    # Parse the file list to obtain the last entry. If its empty use its
    # offset as the size of the CBFS to hash.
    stdout = self._tools.Run('cbfstool',
        [ self.cb_copy, 'print', '-k', '-r', fmap_dst ])
    # Fields are tab separated in the following order.
    # Name    Offset  Type    Metadata Size   Data Size       Total Size
    last_entry = stdout.strip().splitlines()[-1].split('\t')
    if last_entry[0] == '(empty)' and last_entry[2] == 'null':
        size = int(last_entry[1], 16)

    # And extract the blob for the FW section
    rw_section = os.path.join(self._tools.outdir, '_'.join(part_sections))
    self._tools.WriteFile(rw_section,
                          self._tools.ReadFile(self.cb_copy)[base:base+size])

    pack.AddProperty(blob_name, rw_section)

  def _PrepareBootblock(self, pack):
    """Copy bootblock into blob file for packaging

    Args:
      pack: a PackFirmware object describing the firmware image to build.
    Raises:
      CmdError if cbfs-files node has incorrect parameters.
    """
    bootblock_section = os.path.join(self._tools.outdir, 'bootblock.section')

    self._tools.Run('cbfstool', [
      self.cb_copy, 'read', '-r', 'BOOTBLOCK', '-f', bootblock_section])

    pack.AddProperty('bootblock', bootblock_section)

  def _GenerateWiped(self, label, size, value):
    """Fill a CBFS region in cb_copy with a given value

    Args:
      label: fdt-style region name
      size: size of region
      value: value to fill region with (int)
    """
    wipedfile = os.path.join(self._tools.outdir, 'wiped.%s' % label)
    fmaplabel = self._FdtNameToFmap(label)

    self._tools.WriteFile(wipedfile, size*chr(value))
    self._tools.Run('cbfstool', [
      self.cb_copy, 'write',
      '--force',
      '-r', fmaplabel, '-f', wipedfile])

  def _GenerateBlobstring(self, label, size, string):
    """Fill a CBFS region in cb_copy with a given string.
       The remainder of the region will be filled with \x00

    Args:
      label: ftd-style region name
      size: size of region
      string: string to fill in.
    """
    stringfile = os.path.join(self._tools.outdir, 'blobstring.%s' % label)
    fmaplabel = self._FdtNameToFmap(label)

    self._tools.WriteFile(stringfile, (string + size*chr(0))[:size])
    self._tools.Run('cbfstool', [
      self.cb_copy, 'write',
      '--force',
      '-r', fmaplabel, '-f', stringfile])

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
    """
    if blob_type == 'coreboot':
      pass
    elif blob_type == 'legacy':
      self._tools.Run('cbfstool', [self.cb_copy, 'write',
                      '-f', self.seabios_fname,
                      '--force',
                      '-r', 'RW_LEGACY'])
      pack.AddProperty('legacy', self.seabios_fname)
    elif blob_type.startswith('cbfs'):
      self._PrepareCbfs(pack, blob_type)
    elif blob_type == 'bootblock':
      self._PrepareBootblock(pack)
    elif pack.GetProperty(blob_type):
      pass
    elif blob_type == 'ifwi' or blob_type == 'sig2':
      # Copy IFWI/CSE_SIGN(sig2) regions from coreboot copy and build a blob
      # for the blob_type
      blob_start, blob_size = fdt.GetFlashPart('ro', blob_type)
      blob_file = blob_type + '.bin'
      blob_path = os.path.join(self._tools.outdir, blob_file)
      data = self._tools.ReadFile(self.cb_copy)
      self._tools.WriteFile(blob_path, data[blob_start:blob_start+blob_size])
      pack.AddProperty(blob_type, blob_path)
    elif blob_type in self.blobs:
      self._tools.Run('cbfstool', [self.cb_copy, 'write',
                      '--fill-upward',
                      '-f', self.blobs[blob_type],
                      '-r', _FdtNameToFmap(blob_type)])
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
    """
    blob_list = pack.GetBlobList()
    self._out.Info('Building blobs %s\n' % blob_list)

    complete = False
    deferred_list = []

    pack.AddProperty('coreboot', self.bootstub)
    pack.AddProperty('image', self.bootstub)

    for blob_type in blob_list:
      self._BuildBlob(pack, fdt, blob_type)

  def _BuildKeyblocks(self, pack):
    """Compute vblocks and write them into their FMAP regions.
       Works for the (VBLOCK_?,FW_MAIN_?) pairs
    """
    fmap_blob = open(self.coreboot_fname).read()
    f = fmap.fmap_decode(fmap_blob)
    for area in f['areas']:
        label = area['name']
        slot = label[-1]
        if label[:-1] == 'VBLOCK_':
            region_in = 'FW_MAIN_' + slot
            region_out = label

            input_data = os.path.join(self._tools.outdir, 'input.%s' % region_in)
            output_data = os.path.join(self._tools.outdir, 'vblock.%s' % region_out)
            self._tools.Run('cbfstool', [
              self.cb_copy, 'read', '-r', region_in, '-f', input_data])

            # Parse the file list to obtain the last entry. If its empty use
            # its offset as the size of the CBFS to hash.
            stdout = self._tools.Run('cbfstool',
                [ self.cb_copy, 'print', '-k', '-r', region_in ])
            # Fields are tab separated in the following order.
            # Name    Offset  Type    Metadata Size   Data Size     Total Size
            last_entry = stdout.strip().splitlines()[-1].split('\t')
            if last_entry[0] == '(empty)' and last_entry[2] == 'null':
                size = int(last_entry[1], 16)
                self._tools.Run('truncate', [
                    '--no-create', '--size', str(size), input_data])
                self._out.Info('truncated FW_MAIN_%s to %d bytes' %
                    (slot, size))

            try:
              prefix = self._keydir + '/'

              self._tools.Run('vbutil_firmware', [
                  '--vblock', output_data,
                  '--keyblock', prefix + 'firmware.keyblock',
                  '--signprivate', prefix + 'firmware_data_key.vbprivk',
                  '--version', '1',
                  '--fv', input_data,
                  '--kernelkey', prefix + 'kernel_subkey.vbpubk',
                  '--flags', '0',
                ])

            except CmdError as err:
              raise PackError('Cannot make key block: vbutil_firmware failed\n%s' %
                              err)
            self._tools.Run('cbfstool', [self.cb_copy, 'write',
                            '--fill-upward',
                            '-f', output_data,
                            '-r', label])

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
    pack.use_efs = fdt.GetInt('/chromeos-config', 'early-firmware-selection',
                              0)

    pack.SelectFdt(fdt, self._board)

    # Get all our blobs ready
    if self.uboot_fname:
      pack.AddProperty('boot', self.uboot_fname)
    if self.skeleton_fname:
      pack.AddProperty('skeleton', self.skeleton_fname)
    pack.AddProperty('dtb', fdt.fname)

    if gbb:
      pack.AddProperty('gbb', gbb)

    # Build the blobs out.
    self._BuildBlobs(pack, fdt)

    # Now that blobs are built (and written into cb_with_fmap),
    # create the vblocks
    self._BuildKeyblocks(pack)

    self._out.Progress('Packing image')
    if gbb:
      pack.RequireAllEntries()
      self._out.Notice('Firmware ID: %s' % self.fwid)
      pack.AddProperty('fwid', self.fwid)
      pack.AddProperty('keydir', self._keydir)

    pack.CheckProperties()

    # Record position and size of all blob members in the FDT
    pack.UpdateBlobPositionsAndHashes(fdt)

    # Make a copy of the fdt for the bootstub
    fdt_data = self._tools.ReadFile(fdt.fname)
    # Fix up the coreboot image here, since we can't do this until we have
    # a final device tree binary.
    bootstub = pack.GetProperty('coreboot')
    fdt = fdt.Copy(os.path.join(self._tools.outdir, 'bootstub.dtb'))
    if self.coreboot_elf:
      self._tools.Run('cbfstool', [bootstub, 'add-payload', '-f',
          self.coreboot_elf, '-n', 'fallback/payload', '-c', 'lzma'])
    elif self.uboot_fname:
      uboot_data = self._tools.ReadFile(self.uboot_fname)
      uboot_copy = os.path.join(self._tools.outdir, 'u-boot.bin')
      self._tools.WriteFile(uboot_copy, uboot_data)

      uboot_dtb = os.path.join(self._tools.outdir, 'u-boot-dtb.bin')
      self._tools.WriteFile(uboot_dtb, uboot_data + fdt_data)

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

    fdt.Compile(None)
    fdt = fdt.Copy(os.path.join(self._tools.outdir, 'updated.dtb'))
    self.fdt = fdt
    fdt.PutString('/chromeos-config', 'board', self._board)
    if self._force_efs:
      fdt.PutInteger('/chromeos-config', 'early-firmware-selection', 1)
    # If we are writing a kernel, add its offset from TEXT_BASE to the fdt.
    if self.kernel_fname:
      fdt.PutInteger('/config', 'kernel-offset', pack.image_size)


    if fdt.GetProp('/flash', 'reg', ''):
      raise ValueError('fmap.dts /flash is deprecated. Use chromeos.fmd')

    self._CreateCorebootStub(self.coreboot_fname)

    self.fwid = '.'.join([
      re.sub('[ ,]+', '_', fdt.GetString('/', 'model')),
      self._tools.GetChromeosVersion()])

    # fill in /flash from binary fmap
    # ignore "read-only" attribute, that isn't used anywhere
    fmap_blob = open(self.coreboot_fname).read()
    f = fmap.fmap_decode(fmap_blob)
    fdt.PutString('/flash', 'compatible', 'chromeos,flashmap')
    fdt.PutIntList('/flash', 'reg', [f['base'], f['size']])
    for area in f['areas']:
        label = re.sub('_', '-', area['name']).lower()
        fdt_path = '/flash/' + label
        slot=label[-1]
        if label == 'gbb':
            fdt_path = '/flash/ro-gbb'
            fdt.PutString(fdt_path, 'type', 'blob gbb')
            gbb = self._CreateGoogleBinaryBlock()
            gbbdata = (self._tools.ReadFile(gbb) +
                area['size']*'\x00')[:area['size']]
            self._tools.WriteFile(gbb, gbbdata)
            self._tools.Run('cbfstool', [
              self.cb_copy, 'write',
              '-r', 'GBB', '-f', gbb])
        elif label == 'fmap':
            fdt_path = '/flash/ro-fmap'
            fdt.PutString(fdt_path, 'type', 'fmap')
            fdt.PutIntList(fdt_path, 'ver-major', [1])
            fdt.PutIntList(fdt_path, 'ver-minor', [0])
        elif label == 'bootblock':
            fdt.PutString(fdt_path, 'type', 'blob bootblock')
        elif label == 'coreboot':
            fdt_path = '/flash/ro-boot'
            fdt.PutString(fdt_path, 'type', 'blob coreboot')
        elif label == 'si-desc':
            fdt.PutString(fdt_path, 'type', 'ifd')
        elif label == 'rw-shared':
            fdt_path = '/flash/shared-section'
        elif label == 'rw-section-'+slot:
            fdt_path = '/flash/rw-'+slot
        elif label == 'rw-legacy' and self.seabios_fname:
            fdt.PutString(fdt_path, 'type', 'blob legacy')
        elif label in ['rw-mrc-cache', 'recovery-mrc-cache', 'rw-elog',
                       'rw-legacy', 'rw-vpd', 'rw-unused', 'ro-vpd',
                       'ro-unused', 'ro-frid-pad', 'bios-unusable',
                       'device-extension', 'unused-hole', 'rw-gpt-primary',
                       'rw-gpt-secondary', 'rw-nvram', 'ro-unused-1',
                       'ro-unused-2']:
            fdt.PutString(fdt_path, 'type', 'wiped')
            fdt.PutIntList(fdt_path, 'wipe-value', [0xff])
            self._GenerateWiped(label, area['size'], 0xff)
        elif label == 'shared-data':
            fdt.PutString(fdt_path, 'type', 'wiped')
            fdt.PutIntList(fdt_path, 'wipe-value', [0])
            self._GenerateWiped(label, area['size'], 0)
        elif label == 'vblock-dev':
            fdt_path = '/flash/rw-vblock-dev'
            fdt.PutString(fdt_path, 'type', 'wiped')
            fdt.PutIntList(fdt_path, 'wipe-value', [0xff])
            self._GenerateWiped(label, area['size'], 0xff)
        elif label[:-1] == 'vblock-':
            fdt_path = '/flash/rw-'+slot+'-vblock'
            fdt.PutString(fdt_path, 'type', 'keyblock cbfs/rw/'+slot+'-boot')
            fdt.PutString(fdt_path, 'keyblock', 'firmware.keyblock')
            fdt.PutString(fdt_path, 'signprivate', 'firmware_data_key.vbprivk')
            fdt.PutString(fdt_path, 'kernelkey', 'kernel_subkey.vbpubk')
            fdt.PutIntList(fdt_path, 'version', [1])
            fdt.PutIntList(fdt_path, 'preamble-flags', [0])
        elif label[:-1] == 'fw-main-':
            fdt_path = '/flash/rw-'+slot+'-boot'
            fdt.PutString(fdt_path, 'type', 'blob cbfs/rw/'+slot+'-boot')
        elif label[:-1] == 'rw-fwid-':
            fdt_path = '/flash/rw-'+slot+'-firmware-id'
            fdt.PutString(fdt_path, 'type', 'blobstring fwid')
            self._GenerateBlobstring(label, area['size'], self.fwid)
        elif label == 'ro-frid':
            fdt_path = '/flash/ro-firmware-id'
            fdt.PutString(fdt_path, 'type', 'blobstring fwid')
            self._GenerateBlobstring(label, area['size'], self.fwid)
        elif label == 'ifwi':
            fdt_path = '/flash/ro-ifwi'
            fdt.PutString(fdt_path, 'type', 'blob ifwi')
        elif label == 'sign-cse':
            fdt_path = '/flash/ro-sig'
            fdt.PutString(fdt_path, 'type', 'blob sig2')
        # white list for empty regions
        elif label in ['bootblock', 'misc-rw', 'ro-section', 'rw-environment',
		       'rw-gpt', 'si-all', 'si-bios', 'si-me', 'wp-ro',
                       'unified-mrc-cache']:
            pass
        else:
            raise ValueError('encountered label "'+label+'" in binary fmap. '+
                'Check chromeos.fmd')
        fdt.PutString(fdt_path, 'label', label)
        fdt.PutIntList(fdt_path, 'reg', [area['offset'], area['size']])
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
    self.hardware_id = hardware_id
    if self._small or self.fdt.GetProp('/config', 'nogbb', 'any') != 'any':
      gbb = ''  # Building a small image or `nogbb' is requested in device tree.
    else:
      gbb = self._CreateGoogleBinaryBlock()

    # This creates the actual image.
    image, pack = self._CreateImage(gbb, self.fdt)
    if show_map:
      pack.ShowMap()
    if output_fname:
      shutil.copyfile(image, output_fname)
      self._out.Notice("Output image '%s'" % output_fname)
    return image, pack.props
