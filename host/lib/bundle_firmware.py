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
  signed    (uboot + fdt + bct) signed blob
"""

import glob
import os
import re

import shutil
import struct
from tools import CmdError

class Bundle:
  """This class encapsulates the entire bundle firmware logic.

  Sequence of events:
    bundle = Bundle(tools.Tools(), cros_output.Output())
    bundle.SetDirs(...)
    bundle.SetFiles(...)
    bundle.Start(...)
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
    self._keydir = None
    self.coreboot_elf = None
    self.coreboot_fname = None  # Filename of our coreboot binary.
    self.ecro_fname = None      # Filename of EC read-only file
    self.ecrw_fname = None      # Filename of EC file
    self.pdrw_fname = None      # Filename of PD file
    self.kernel_fname = None
    self.seabios_fname = None   # Filename of our SeaBIOS payload.
    self.uboot_fname = None     # Filename of our U-Boot binary.
    self.cb_copy = None

  def SetDirs(self, keydir):
    """Set up directories required for Bundle.

    Args:
      keydir: Directory containing keys to use for signing firmware.
    """
    self._keydir = keydir

  def SetFiles(self, board, uboot=None, coreboot=None,
               coreboot_elf=None,
               seabios=None,
               ecrw=None, ecro=None, pdrw=None,
               kernel=None, cbfs_files=None,
               rocbfs_files=None):
    """Set up files required for Bundle.

    Args:
      board: The name of the board to target (e.g. nyan).
      uboot: The filename of the u-boot.bin image to use.
      coreboot: The filename of the coreboot image to use (on x86).
      coreboot_elf: If not none, the ELF file to add as a Coreboot payload.
      seabios: The filename of the SeaBIOS payload to use if any.
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
    self.ecrw_fname = ecrw
    self.ecro_fname = ecro
    self.pdrw_fname = pdrw
    self.kernel_fname = kernel
    self.cbfs_files = cbfs_files
    self.rocbfs_files = rocbfs_files

  def _AddCbfsFiles(self, cbfs_files, regions='COREBOOT'):
    for dir, subs, files in os.walk(cbfs_files):
      for file in files:
        file = os.path.join(dir, file)
        cbfs_name = file.replace(cbfs_files, '', 1).strip('/')
        self._tools.Run('cbfstool', [self.cb_copy, 'add', '-f', file,
                                '-n', cbfs_name, '-t', 'raw', '-c', 'lzma',
                                '-r', regions])

  def _CreateCorebootStub(self, coreboot):
    """Create a coreboot boot stub.

    Args:
      coreboot: Path to coreboot.rom
    """
    # Create a coreboot copy to use as a scratch pad.
    shutil.copyfile(self._tools.Filename(coreboot), self.cb_copy)

    # Add files to to RO and RW CBFS if provided.
    if self.cbfs_files:
      self._AddCbfsFiles(self.cbfs_files,
          'COREBOOT,FW_MAIN_A,FW_MAIN_B')

    # Add files to to RO CBFS if provided.
    if self.rocbfs_files:
      self._AddCbfsFiles(self.rocbfs_files)

    # Fix up the coreboot image here, since we can't do this until we have
    # a final device tree binary.
    self._tools.Run('cbfstool', [self.cb_copy, 'add-payload', '-f',
        self.coreboot_elf, '-n', 'fallback/payload', '-c', 'lzma'])


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

  def _BuildKeyblocks(self, slot):
    """Compute vblocks and write them into their FMAP regions.
       Works for the (VBLOCK_?,FW_MAIN_?) pairs

    Args:
      slot: 'A' or 'B'
    """
    region_in = 'FW_MAIN_' + slot
    region_out = 'VBLOCK_' + slot

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
        trunc_data = trunc_data[:size]
        self._tools.WriteFile(input_data, trunc_data)
        self._tools.Run('cbfstool', [
          self.cb_copy, 'write',
          '--force', '-u', '-i', '0',
          '-r', region_in, '-f', input_data])
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
                    '-f', output_data, '-u', '-i', '0',
                    '-r', 'VBLOCK_'+slot])

  def _CreateImage(self):
    """Create a full firmware image, along with various by-products.

    This uses the provided files to create a firmware
    image containing all the required parts. If the GBB is not supplied
    then this will just return a signed U-Boot as the image.

    Returns:
      Path to image file
    """
    self._PrepareCbfs('FW_MAIN_A')
    self._PrepareCbfs('FW_MAIN_B')

    # Now that RW CBFSes are final, create the vblocks
    self._BuildKeyblocks('A')
    self._BuildKeyblocks('B')

  def Start(self, output_fname, show_map):
    """This creates a firmware bundle according to settings provided.

      - Checks options, tools, output directory.
      - Creates GBB and image.

    Args:
      output_fname: Output filename for the image. If this is not None, then
          the final image will be copied here.
      show_map: Show a flash map, with each area's name and position

    Returns:
      Filename of the resulting image (not the output_fname copy).
    """
    self.cb_copy = output_fname
    self._CreateCorebootStub(self.coreboot_fname)

    if self.seabios_fname:
        self._tools.Run('cbfstool', [self.cb_copy, 'write',
                        '-f', self.seabios_fname,
                        '--force',
                        '-r', 'RW_LEGACY'])
    # This creates the actual image.
    self._CreateImage()
    if show_map:
      self._tools.Run('cbfstool', [self.cb_copy, 'layout', '-w'])
    self._out.Notice("Output image '%s'" % output_fname)
