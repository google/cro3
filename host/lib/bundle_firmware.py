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
    self.coreboot_elf = None
    self.coreboot_fname = None  # Filename of our coreboot binary.
    self.ecro_fname = None      # Filename of EC read-only file
    self.ecrw_fname = None      # Filename of EC file
    self.pdrw_fname = None      # Filename of PD file
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

  def SetFiles(self, board, uboot=None, coreboot=None,
               coreboot_elf=None,
               seabios=None,
               skeleton=None, ecrw=None, ecro=None, pdrw=None,
               kernel=None, cbfs_files=None,
               rocbfs_files=None):
    """Set up files required for Bundle.

    Args:
      board: The name of the board to target (e.g. nyan).
      uboot: The filename of the u-boot.bin image to use.
      coreboot: The filename of the coreboot image to use (on x86).
      coreboot_elf: If not none, the ELF file to add as a Coreboot payload.
      seabios: The filename of the SeaBIOS payload to use if any.
      skeleton: The filename of the coreboot skeleton file.
      ecrw: The filename of the EC (Embedded Controller) read-write file.
      ecro: The filename of the EC (Embedded Controller) read-only file.
      pdrw: The filename of the PD (PD embedded controller) read-write file.
      kernel: The filename of the kernel file if any.
      cbfs_files: Root directory of files to be stored in RO and RW CBFS
      rocbfs_files: Root directory of files to be stored in RO CBFS
    """
    self._board = board
    self.uboot_fname = uboot
    self.coreboot_fname = coreboot
    self.coreboot_elf = coreboot_elf
    self.seabios_fname = seabios
    self.skeleton_fname = skeleton
    self.ecrw_fname = ecrw
    self.ecro_fname = ecro
    self.pdrw_fname = pdrw
    self.kernel_fname = kernel
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

    # Make a copy of the fdt for the bootstub
    fdt_data = self._tools.ReadFile(self.fdt.fname)
    # Fix up the coreboot image here, since we can't do this until we have
    # a final device tree binary.
    fdt = self.fdt.Copy(os.path.join(self._tools.outdir, 'bootstub.dtb'))
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

    # Create a coreboot copy to use as a scratch pad.
    cb_copy = os.path.abspath(os.path.join(self._tools.outdir, 'cb_with_fmap'))
    self._tools.WriteFile(cb_copy, self._tools.ReadFile(bootstub))
    binary = self._tools.ReadFile(bootstub)
    self._tools.WriteFile(cb_copy, binary)
    self.cb_copy = cb_copy

  def _PrepareCbfs(self, fmap_dst):
    """Prepare CBFS in given FMAP section.

    Add some of our additional RW files: payload and EC firmware.

    If --coreboot-elf parameter was specified during cros_bumdle_firmware
    invocation, add the parameter of this option as the payload to the new
    CBFS instance.

    Args:
      fmap_dst: a string, fmap region to work with.
    Raises:
      CmdError if cbfs-files node has incorrect parameters.
    """

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

  def _GenerateWiped(self, label, size, value):
    """Fill a CBFS region in cb_copy with a given value

    Args:
      label: fdt-style region name
      size: size of region
      value: value to fill region with (int)
    """
    wipedfile = os.path.join(self._tools.outdir, 'wiped.%s' % label)

    self._tools.WriteFile(wipedfile, size*chr(value))
    self._tools.Run('cbfstool', [
      self.cb_copy, 'write',
      '--force',
      '-r', label, '-f', wipedfile])

  def _GenerateBlobstring(self, label, size, string):
    """Fill a CBFS region in cb_copy with a given string.
       The remainder of the region will be filled with \x00

    Args:
      label: ftd-style region name
      size: size of region
      string: string to fill in.
    """
    stringfile = os.path.join(self._tools.outdir, 'blobstring.%s' % label)

    self._tools.WriteFile(stringfile, (string + size*chr(0))[:size])
    self._tools.Run('cbfstool', [
      self.cb_copy, 'write',
      '--force',
      '-r', label, '-f', stringfile])

  def _BuildKeyblocks(self):
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
                trunc_data = self._tools.ReadFile(input_data)
                full_size = len(trunc_data)
                trunc_data = trunc_data[:size]
                trunc_data = (trunc_data + full_size*'\x00')[:full_size]
                self._tools.WriteFile(input_data, trunc_data)
                self._tools.Run('cbfstool', [
                  self.cb_copy, 'write',
                  '--force',
                  '-r', region_in, '-f', input_data])
                trunc_data = trunc_data[:size]
                self._tools.WriteFile(input_data, trunc_data)
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
              filedata = self._tools.ReadFile(output_data)
              filedata = (filedata + area['size']*'\x00')[:area['size']]
              self._tools.WriteFile(output_data, filedata)

            except CmdError as err:
              raise PackError('Cannot make key block: vbutil_firmware failed\n%s' %
                              err)
            self._tools.Run('cbfstool', [self.cb_copy, 'write',
                            '-f', output_data,
                            '-r', label])

  def _PrepareIfd(self):
    """Produce the final image for an Intel ME system

    Some Intel systems require that an image contains the Management Engine
    firmware, and also a firmware descriptor.

    This function takes the existing image, removes the front part of it,
    and replaces it with these required pieces using ifdtool.

    Args:
      image_fname: Output image filename
    """
    tools = self._tools
    out = self._out
    tmpdir = self._tools.outdir
    image_fname = self.cb_copy

    out.Progress('Setting up Intel ME')
    data = tools.ReadFile(image_fname)

    # Calculate start and size of BIOS region based off the IFD descriptor and
    # not the size in dts node.
    ifd_layout_tmp = os.path.join(tmpdir, 'ifd-layout-tmp')
    args = ['-f%s' % ifd_layout_tmp, tools.Filename(self.skeleton_fname)]
    tools.Run('ifdtool', args)
    fd = open(ifd_layout_tmp)
    layout = fd.readlines()
    for line in layout:
        line = line.rstrip()
        if line.find("bios") != -1:
            addr_range = line.split(' ')[0]
            start = int(addr_range.split(':')[0], 16)
            end = int(addr_range.split(':')[1], 16)

    fd.close()

    data = data[start:end+1]
    input_fname = os.path.join(tmpdir, 'ifd-input.bin')
    tools.WriteFile(input_fname, data)
    ifd_output = os.path.join(tmpdir, 'image.ifd')

    # This works by modifying a skeleton file.
    shutil.copyfile(tools.Filename(self.skeleton_fname), ifd_output)
    args = ['-i', 'BIOS:%s' % input_fname, ifd_output]
    tools.Run('ifdtool', args)

    # ifdtool puts the output in a file with '.new' tacked on the end.
    shutil.move(ifd_output + '.new', image_fname)
    tools.OutputSize('IFD image', image_fname)

  def _CreateImage(self, fdt):
    """Create a full firmware image, along with various by-products.

    This uses the provided u-boot.bin, fdt and bct to create a firmware
    image containing all the required parts. If the GBB is not supplied
    then this will just return a signed U-Boot as the image.

    Args:
      fdt: an fdt object containing required information.

    Returns:
      Path to image file
    """
    self._out.Notice("Model: %s" % fdt.GetString('/', 'model'))

    self._PrepareCbfs('FW_MAIN_A')
    self._PrepareCbfs('FW_MAIN_B')

    # Now that RW CBFSes are final, create the vblocks
    self._BuildKeyblocks()

    self._out.Notice('Firmware ID: %s' % self.fwid)

    shutil.copyfile(self.bootstub,
        os.path.join(self._tools.outdir, 'coreboot-8mb.rom'))

    self._tools.Run('cbfstool', [self.cb_copy, 'read',
            '-r', 'COREBOOT',
            '-f', self.bootstub])

  def SelectFdt(self, fdt_fname):
    """Select an FDT to control the firmware bundling

    We make a copy of this which will include any on-the-fly changes we want
    to make.

    Args:
      fdt_fname: The filename of the fdt to use.

    Returns:
      The Fdt object of the original fdt file, which we will not modify.

    Raises:
      ValueError if no FDT is provided (fdt_fname is None).
    """
    if not fdt_fname:
      raise ValueError('Please provide an FDT filename')
    fdt = Fdt(self._tools, fdt_fname)
    self._fdt_fname = fdt_fname

    fdt.Compile(None)
    fdt = fdt.Copy(os.path.join(self._tools.outdir, 'updated.dtb'))
    self.fdt = fdt
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
    for area in f['areas']:
        label = area['name']
        if label == 'GBB':
            gbb = self._CreateGoogleBinaryBlock()
            gbbdata = (self._tools.ReadFile(gbb) +
                area['size']*'\x00')[:area['size']]
            self._tools.WriteFile(gbb, gbbdata)
            self._tools.Run('cbfstool', [
              self.cb_copy, 'write',
              '-r', 'GBB', '-f', gbb])
        elif label == 'SI_DESC':
            self._PrepareIfd()
        elif label == 'RW_LEGACY' and self.seabios_fname:
            self._tools.Run('cbfstool', [self.cb_copy, 'write',
                            '-f', self.seabios_fname,
                            '--force',
                            '-r', 'RW_LEGACY'])
        elif label in ['RW_MRC_CACHE', 'RECOVERY_MRC_CACHE', 'RW_ELOG',
                       'RW_LEGACY', 'RW_VPD', 'RW_UNUSED', 'RO_VPD',
                       'RO_UNUSED', 'RO_FRID_PAD', 'BIOS_UNUSABLE',
                       'DEVICE_EXTENSION', 'UNUSED_HOLE', 'RW_GPT_PRIMARY',
                       'RW_GPT_SECONDARY', 'RW_NVRAM', 'RO_UNUSED_1',
                       'RO_UNUSED_2', 'RW_VAR_MRC_CACHE']:
            self._GenerateWiped(label, area['size'], 0xff)
        elif label == 'SHARED_DATA':
            self._GenerateWiped(label, area['size'], 0)
        elif label == 'VBLOCK_DEV':
            self._GenerateWiped(label, area['size'], 0xff)
        elif label[:-1] == 'RW_FWID_':
            self._GenerateBlobstring(label, area['size'], self.fwid)
        elif label == 'RO_FRID':
            self._GenerateBlobstring(label, area['size'], self.fwid)
        # white list for empty regions
        elif label in ['BOOTBLOCK', 'MISC_RW', 'RO_SECTION', 'RW_ENVIRONMENT',
		       'RW_GPT', 'SI_ALL', 'SI_BIOS', 'SI_ME', 'WP_RO',
                       'SIGN_CSE', 'IFWI', 'FMAP', 'BOOTBLOCK', 'COREBOOT',
                       'RW_SHARED', 'RW_SECTION_A', 'RW_SECTION_B',
                       'VBLOCK_A', 'VBLOCK_B', 'FW_MAIN_A', 'FW_MAIN_B',
                       'UNIFIED_MRC_CACHE']:
            pass
        else:
            raise ValueError('encountered label "'+label+'" in binary fmap. '+
                'Check chromeos.fmd')

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

    # This creates the actual image.
    self._CreateImage(self.fdt)
    if show_map:
      self._tools.Run('cbfstool', [self.cb_copy, 'layout', '-w'])
    if output_fname:
      shutil.copyfile(self.cb_copy, output_fname)
      self._out.Notice("Output image '%s'" % output_fname)
    return self.cb_copy, self.bootstub
