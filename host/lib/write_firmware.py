# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import binascii
import glob
import os
import re
import struct
import time

from exynos import ExynosBl2
from tools import CmdError

def RoundUp(value, boundary):
  """Align a value to the next power of 2 boundary.

  Args:
    value: The value to align.
    boundary: The boundary value, e.g. 4096. Must be a power of 2.

  Returns:
    The rounded-up value.
  """
  return (value + boundary - 1) & ~(boundary - 1)


class WriteFirmware:
  """Write firmware to a Tegra 2 board using USB A-A cable.

  This class handles re-reflashing a board with new firmware using the Tegra's
  built-in boot ROM feature. This works by putting the chip into a special mode
  where it ignores any available firmware and instead reads it from a connected
  host machine over USB.

  In our case we use that feature to send U-Boot along with a suitable payload
  and instructions to flash it to SPI flash. The payload is itself normally a
  full Chrome OS image consisting of U-Boot, some keys and verification
  information, images and a map of the flash memory.

  Private attributes:
    _servo_port: Port number to use to talk to servo with dut-control.
      Special values are:
        None: servo is not available.
        0: any servo will do.

  """

  _DOWNLOAD_FAILURE_MESSAGE = '** Load checksum error: check download tool **'
  _SKIP_VERIFY_MESSAGE = 'Skipping verify'
  _WRITE_FAILURE_MESSAGE = '** Readback checksum error, programming failed!! **'
  _WRITE_SUCCESS_MESSAGE = 'Image Programmed Successfully'

  def __init__(self, tools, fdt, output, bundle, update, verify):
    """Set up a new WriteFirmware object.

    Args:
      tools: A tools library for us to use.
      fdt: An fdt which gives us some info that we need.
      output: An output object to use for printing progress and messages.
      bundle: A BundleFirmware object which created the image.
      update: Use faster update algorithm rather then full device erase.
      verify: Verify the write by doing a readback and CRC.
    """
    self._tools = tools
    self._fdt = fdt
    self._out = output
    self._bundle = bundle
    self.text_base = self._fdt.GetInt('/chromeos-config', 'textbase', -1)

    # For speed, use the 'update' algorithm and don't verify
    self.update = update
    self.verify = verify

    # Use default servo port
    self._servo_port = 0

    # By default, no early firmware selection.
    self.use_efs = False

  def SelectServo(self, servo):
    """Select the servo to use for writing firmware.

    Args:
      servo: String containing description of servo to use:
        'none'  : Don't use servo, generate an error on any attempt.
        'any'   : Use any available servo.
        '<port>': Use servo with that port number.
    """
    if servo == 'none':
      self._servo_port = None
    elif servo == 'any':
      self._servo_port = 0
    else:
      self._servo_port = int(servo)
    self._out.Notice('Servo port %s' % str(self._servo_port))

  def _GetFlashScript(self, payload_size, flash_dest, checksum, ro_size=None):
    """Get the U-Boot boot command needed to flash U-Boot.

    We leave a marker in the string for the load address of the image,
    since this depends on the size of this script. This can be replaced by
    the caller provided that the marker length is unchanged.

    Args:
      payload_size: Size of payload in bytes.
      flash_dest: A dictionary of strings keyed by 'type' (nand, sdmmc,
                  or spi), 'bus', and 'dev'.
      checksum: The checksum of the payload (an integer)
      ro_size: Size of read-only partition.  If set, split MMC image between
               partition 1 (ro) and partition 2 (rw).

    Returns:
      A tuple containing:
        The script, as a string ready to use as a U-Boot boot command, with an
            embedded marker for the load address.
        The marker string, which the caller should replace with the correct
            load address as 8 hex digits, without changing its length.
        The marker RW string, which the caller should replace with the correct
            load address for the RW section as 8 hex digits, without changing
            its length.  This is only required if ro_size is set.
    """
    replace_me = 'zsHEXYla'
    replace_me_rw = 'zsHEXYrw'
    page_size = 4096
    boot_type = flash_dest['type']
    if boot_type == 'sdmmc':
      page_size = 512
    update = self.update and boot_type == 'spi'

    cmds = [
        'setenv address       0x%s' % replace_me,
        'setenv firmware_size %#x' % payload_size,
        'setenv length        %#x' % RoundUp(payload_size, page_size),
        'setenv blocks   %#x' % (RoundUp(payload_size, page_size) / page_size),
        'setenv _crc    "crc32 -v ${address} ${firmware_size} %08x"' %
            checksum,
        'setenv _clear  "echo Clearing RAM; mw.b     ${address} 0 ${length}"',
    ]

    if ro_size:
      rw_size = payload_size - ro_size

      cmds.extend([
        'setenv address_ro   ${address}',
        'setenv address_rw   0x%s' % replace_me_rw,
        'setenv blocks_ro    %#x' % (RoundUp(ro_size, page_size) / page_size),
        'setenv blocks_rw    %#x' % (RoundUp(rw_size, page_size) / page_size),
      ])

    if boot_type == 'nand':
      cmds.extend([
          'setenv _init   "echo Init NAND;  nand info"',
          'setenv _erase  "echo Erase NAND; nand erase            0 ${length}"',
          'setenv _write  "echo Write NAND; nand write ${address} 0 ${length}"',
          'setenv _read   "echo Read NAND;  nand read  ${address} 0 ${length}"',
      ])
    elif boot_type == 'sdmmc':
      # In U-Boot, strings in double quotes have variables expanded to actual
      # values.  For reasons unclear, this expansion splits the single quoted
      # argument into separate arguements for each word, which on exynos
      # boards causes the command to exceed the maximum configured argument
      # count. Passing the string in single quotes prevents this expansion,
      # allowing variables to be expanded when run is called.
      # crbug.com/260294
      cmds.extend([
          'setenv _init   "echo Init EMMC;  mmc rescan"',
          'setenv _erase  "echo Erase EMMC; "',
      ])
      if ro_size:
        # Write RO section to partition 1, RW to partition 2
        cmds.extend([
            "setenv _write  'echo Write EMMC;"  \
              "              mmc open 0 1;" \
              "              mmc write ${address_ro} 0 ${blocks_ro};" \
              "              mmc close 0 1;" \
              "              mmc open 0 2;" \
              "              mmc write ${address_rw} 0 ${blocks_rw};" \
              "              mmc close 0 2'",
            "setenv _read   'echo Read EMMC;"  \
              "              mmc open 0 1;" \
              "              mmc read ${address_ro} 0 ${blocks_ro};" \
              "              mmc close 0 1;" \
              "              mmc open 0 2;" \
              "              mmc read ${address_rw} 0 ${blocks_rw};" \
              "              mmc close 0 2'",
        ])
      else:
        cmds.extend([
            "setenv _write  'echo Write EMMC;" \
              "              mmc open 0 1;" \
              "              mmc write ${address} 0 ${blocks};" \
              "              mmc close 0 1'",
            "setenv _read   'echo Read EMMC;" \
              "              mmc open 0 1;" \
              "              mmc read ${address} 0 ${blocks};" \
              "              mmc close 0 1'",
        ])
    else:
      if flash_dest['bus'] is None:
        flash_dest['bus'] = '0'
      if flash_dest['dev'] is None:
        flash_dest['dev'] = '0'
      cmds.extend([
          'setenv _init   "echo Init SPI;   sf probe            %s:%s"' %
              (flash_dest['bus'], flash_dest['dev']),
          'setenv _erase  "echo Erase SPI;  sf erase            0 ${length}"',
          'setenv _write  "echo Write SPI;  sf write ${address} 0 ${length}"',
          'setenv _read   "echo Read SPI;   sf read  ${address} 0 ${length}"',
          'setenv _update "echo Update SPI; sf update ${address} 0 ${length}"',
      ])

    cmds.extend([
        'echo Firmware loaded to ${address}, size ${firmware_size}, '
            'length ${length}',
        'if run _crc; then',
        'run _init',
    ])
    if update:
      cmds += ['time run _update']
    else:
      cmds += ['run _erase', 'run _write']
    if self.verify:
      cmds += [
        'run _clear',
        'run _read',
        'if run _crc; then',
        'echo "%s"' % self._WRITE_SUCCESS_MESSAGE,
        'else',
        'echo',
        'echo "%s"' % self._WRITE_FAILURE_MESSAGE,
        'echo',
        'fi',
      ]
    else:
      cmds += ['echo %s' % self._SKIP_VERIFY_MESSAGE]
    cmds.extend([
      'else',
      'echo',
      'echo "%s"' % self._DOWNLOAD_FAILURE_MESSAGE,
      'fi',
      ])
    script = '; '.join(cmds)
    return script, replace_me, replace_me_rw

  def _ReplaceAddr(self, data, replace_me, replacement):
    """Replace address in FDT

    Detect and replace a placeholder address in the FDT.

    Args:
      data: FDT data to do replacement on
      replace_me: String currently in FDT to replace
      replacement: Replacement string

    Returns:
      Updated data with replacement
    """
    if len(replace_me) is not len(replacement):
      raise ValueError("Internal error: replacement string '%s' length does "
          "not match new string '%s'" % (replace_me, replacement))

    matches = len(re.findall(replace_me, data))
    if matches != 1:
      raise ValueError("Internal error: replacement string '%s' already "
          "exists in the fdt (%d matches)" % (replace_me, matches))

    return re.sub(replace_me, replacement, data)

  def _PrepareFlasher(self, uboot, payload, flash_dest, ro_size=None):
    """Get a flasher ready for sending to the board.

    The flasher is an executable image consisting of:

      - U-Boot (u-boot.bin);
      - a special FDT to tell it what to do in the form of a run command;
      - (we could add some empty space here, in case U-Boot is not built to
          be relocatable);
      - the payload (which is a full flash image, or signed U-Boot + fdt).

    Args:
      uboot: Full path to u-boot.bin.
      payload: Full path to payload.
      flash_dest: A dictionary of strings keyed by 'type' (nand, sdmmc,
                  or spi), 'bus', and 'dev'.
      boot_type: the src for bootdevice (nand, sdmmc, or spi)
      ro_size: Size of read-only partition on emmc.  If set, indicates that
               the image should be split, with half written to partition 1, and
               half written to partition 2.

    Returns:
      Filename of the flasher binary created.
    """
    fdt = self._fdt.Copy(os.path.join(self._tools.outdir, 'flasher.dtb'))
    fdt.PutInteger('/config', 'bootsecure', 0)
    fdt.PutInteger('/config', 'silent-console', 0)
    payload_data = self._tools.ReadFile(payload)

    # Make sure that the checksum is not negative
    checksum = binascii.crc32(payload_data) & 0xffffffff

    script, replace_start, replace_rw = self._GetFlashScript(len(payload_data),
                                          flash_dest, checksum, ro_size)
    data = self._tools.ReadFile(uboot)
    fdt.PutString('/config', 'bootcmd', script)
    fdt_data = self._tools.ReadFile(fdt.fname)

    # Work out where to place the payload in memory. This is a chicken-and-egg
    # problem (although in case you haven't heard, it was the chicken that
    # came first), so we resolve it by replacing the string after
    # fdt.PutString has done its job.
    #
    # Correction: Technically, the egg came first. Whatever genetic mutation
    # created the new species would have been present in the egg, but not the
    # parent (since if it was in the parent, it would have been present in the
    # parent when it was an egg).
    #
    # Question: ok so who laid the egg then?
    payload_offset = len(data) + len(fdt_data)

    # NAND driver expects 4-byte alignment.  Just go whole hog and do 4K.
    alignment = 0x1000
    payload_offset = (payload_offset + alignment - 1) & ~(alignment - 1)

    load_address = self.text_base + payload_offset,
    new_str = '%08x' % load_address
    fdt_data = self._ReplaceAddr(fdt_data, replace_start, new_str)

    if ro_size:
      new_str_rw = '%08x' % (load_address[0] + ro_size)
      fdt_data = self._ReplaceAddr(fdt_data, replace_rw, new_str_rw)

    # Now put it together.
    data += fdt_data
    data += "\0" * (payload_offset - len(data))
    data += payload_data
    flasher = os.path.join(self._tools.outdir, 'flasher-for-image.bin')
    self._tools.WriteFile(flasher, data)

    # Tell the user about a few things.
    self._tools.OutputSize('U-Boot', uboot)
    self._tools.OutputSize('Payload', payload)
    self._out.Notice('Payload checksum %08x' % checksum)
    self._tools.OutputSize('Flasher', flasher)
    return flasher

  def NvidiaFlashImage(self, flash_dest, uboot, bct, payload, bootstub):
    """Flash the image to SPI flash.

    This creates a special Flasher binary, with the image to be flashed as
    a payload. This is then sent to the board using the tegrarcm utility.

    Args:
      flash_dest: Destination for flasher, or None to not create a flasher.
          This value is a dictionary of strings keyed by 'type', 'bus', and
          'dev'.
      uboot: Full path to u-boot.bin.
      bct: Full path to BCT file (binary chip timings file for Nvidia SOCs).
      payload: Full path to payload.
      bootstub: Full path to bootstub, which is the payload without the
          signing information (i.e. bootstub is u-boot.bin + the FDT)

    Returns:
      True if ok, False if failed.
    """
    # Use a Regex to pull Boot type from BCT file.
    match = re.compile('DevType\[0\] = NvBootDevType_(?P<boot>([a-zA-Z])+);')
    bct_dumped = self._tools.Run('bct_dump', [bct]).splitlines()

    # TODO(sjg): The boot type is currently selected by the bct, rather than
    # flash_dest['type'] selecting which bct to use. This is a bit backwards.
    # For now we go with the bct's idea.
    flash_dest['type'] = filter(match.match, bct_dumped)
    flash_dest['type'] = match.match(
        flash_dest['type'][0]).group('boot').lower()

    if flash_dest:
      image = self._PrepareFlasher(uboot, payload, flash_dest)
    elif bootstub:
      image = bootstub

    else:
      image = payload
      # If we don't know the textbase, extract it from the payload.
      if self.text_base == -1:
        data = self._tools.ReadFile(payload)
        # Skip the BCT which is the first 64KB
        self.text_base = self._bundle.DecodeTextBase(data[0x10000:])

    self._out.Notice('TEXT_BASE is %#x' % self.text_base)
    self._out.Progress('Uploading flasher image')
    args = [
      '--bct', bct,
      '--bootloader',  image,
      '--loadaddr', "%#x" % self.text_base
    ]

    # TODO(sjg): Check for existence of board - but chroot has no lsusb!
    last_err = None
    for _ in range(10):
      try:
        # TODO(sjg): Use Chromite library so we can monitor output
        self._tools.Run('tegrarcm', args, sudo=True)
        self._out.Notice('Flasher downloaded - please see serial output '
            'for progress.')
        return True

      except CmdError as err:
        if not self._out.stdout_is_tty:
          return False

        # Only show the error output once unless it changes.
        err = str(err)
        if not 'could not open USB device' in err:
          raise CmdError('tegrarcm failed: %s' % err)

        if err != last_err:
          self._out.Notice(err)
          last_err = err
          self._out.Progress('Please connect USB A-A cable and do a '
              'recovery-reset', True)
        time.sleep(1)

    return False

  def _WaitForUSBDevice(self, name, vendor_id, product_id, timeout=10):
    """Wait until we see a device on the USB bus.

    Args:
      name: Board type name
      vendor_id: USB vendor ID to look for
      product_id: USB product ID to look for
      timeout: Timeout to wait in seconds

    Returns
      True if the device was found, False if we timed out.
    """
    self._out.Progress('Waiting for board to appear on USB bus')
    start_time = time.time()
    while time.time() - start_time < timeout:
      try:
        args = ['-d', '%04x:%04x' % (vendor_id, product_id)]
        self._tools.Run('lsusb', args, sudo=True)
        self._out.Progress('Found %s board' % name)
        return True

      except CmdError:
        pass

    return False

  def DutControl(self, args):
    """Run dut-control with supplied arguments.

    The correct servo will be used based on self._servo_port. If servo use is
    disabled, this function does nothing.

    Args:
      args: List of arguments to dut-control.

    Returns:
      a string, stdout generated by running the command
    """
    if self._servo_port is None:
      return ''  # User has requested not to use servo
    if self._servo_port:
      args.extend(['-p', '%s' % self._servo_port])
    return self._tools.Run('dut-control', args)

  def WaitForCompletion(self):
    """Verify flash programming operation success.

    The DUT is presumed to be programming flash with console capture mode on.
    This function scans console output for the success or failure strings.

    Raises:
      CmdError if the following cases:
        - none of the strings show up in the allotted time (2 minutes)
        - console goes silent for more than 10 seconds
        - one of the error messages seen in the stream
        - misformatted output is seen in the stream
    """

    _SOFT_DEADLINE_LIMIT = 10
    _HARD_DEADLINE_LIMIT = 120
    string_leftover = ''
    soft_deadline = time.time() + _SOFT_DEADLINE_LIMIT
    hard_deadline = soft_deadline + _HARD_DEADLINE_LIMIT - _SOFT_DEADLINE_LIMIT

    if self.verify:
      done_line = self._WRITE_SUCCESS_MESSAGE
    else:
      done_line = self._SKIP_VERIFY_MESSAGE

    while True:
      now = time.time()
      if now > hard_deadline:
        raise CmdError('Target console flooded, programming failed')
      if now > soft_deadline:
        raise CmdError('Target console dead, programming failed')
      stream = self.DutControl(['cpu_uart_stream',])
      match = re.search("^cpu_uart_stream:['\"](.*)['\"]\n", stream)
      if not match:
        raise CmdError('Misformatted console output: \n%s\n' % stream)

      text = string_leftover + match.group(1)
      strings = text.split('\\r')
      string_leftover = strings.pop()
      if strings:
        soft_deadline = now + _SOFT_DEADLINE_LIMIT
        for string in strings:
          if done_line in string:
            return True
          if self._WRITE_FAILURE_MESSAGE in string:
            raise CmdError('Readback verification failed!')
          if self._DOWNLOAD_FAILURE_MESSAGE in string:
            raise CmdError('Download failed!')

  def _ExtractPayloadParts(self, payload, truncate_to_fdt):
    """Extract the BL1, BL2 and U-Boot parts from a payload.

    An exynos image consists of 3 parts: BL1, BL2 and U-Boot/FDT.

    This pulls out the various parts, puts them into files and returns
    these files.

    Args:
      payload: Full path to payload.
      truncate_to_fdt: Truncate the U-Boot image at the start of its
        embedded FDT

    Returns:
      (bl1, bl2, image, uboot_offset) where:
        bl1 is the filename of the extracted BL1
        bl2 is the filename of the extracted BL2
        image is the filename of the extracted U-Boot image
        uboot_offset is the offset of U-Boot in the image
    """
    # Pull out the parts from the payload
    bl1 = os.path.join(self._tools.outdir, 'bl1.bin')
    bl2 = os.path.join(self._tools.outdir, 'bl2.bin')
    image = os.path.join(self._tools.outdir, 'u-boot-from-image.bin')
    data = self._tools.ReadFile(payload)

    try:
      bl1_size = int(self._fdt.GetProps('/flash/pre-boot')['size'])
      bl2_size = int(self._fdt.GetProps('/flash/spl')['size'])
      uboot_offset = bl1_size + bl2_size
    except (CmdError, KeyError):
      self._out.Warning('No component nodes in the device tree')
      # The BL1 is always 8KB - extract that part into a new file
      # TODO(sjg@chromium.org): Perhaps pick these up from the fdt?
      bl1_size = 0x2000

      # Try to detect the BL2 size. We look for 0xea000014 or 0xea000013
      # which is the 'B reset' instruction at the start of U-Boot. When
      # U-Boot is LZO compressed, we look for a LZO magic instead.
      start_data = [struct.pack('<L', 0xea000014),
                    struct.pack('<L', 0xea000013),
                    struct.pack('>B3s', 0x89, 'LZO')]
      starts = [data.find(magic, bl1_size + 0x3800) for magic in start_data]
      uboot_offset = None
      for start in starts:
        if start != -1 and (not uboot_offset or start < uboot_offset):
          uboot_offset = start
      if not uboot_offset:
        raise ValueError('Could not locate start of U-Boot')
      bl2_size = uboot_offset - bl1_size - 0x800  # 2KB gap after BL2

      # Sanity check: At present we only allow 14KB and 30KB for SPL
      allowed = [14, 30]
      if (bl2_size >> 10) not in allowed:
        raise ValueError('BL2 size is %dK - only %s supported' %
                         (bl2_size >> 10, ', '.join(
              [str(size) for size in allowed])))
    self._out.Notice('BL2 size is %dKB' % (bl2_size >> 10))

    self._tools.WriteFile(bl1, data[:bl1_size])
    self._tools.WriteFile(bl2, data[bl1_size:bl1_size + bl2_size])

    # U-Boot itself starts at 24KB, after the gap. As a hack, truncate it
    # to an assumed maximum size. As a secondary hack, locate the FDT
    # and truncate U-Boot from that point. The correct FDT will be added
    # when the image is written to the board.
    # TODO(sjg@chromium.org): Get a proper flash map here so we know how
    # large it is
    uboot_data = data[uboot_offset:uboot_offset + 0xa0000]
    if truncate_to_fdt:
      fdt_magic = struct.pack('>L', 0xd00dfeed)
      fdt_offset = uboot_data.rfind(fdt_magic)
      uboot_data = uboot_data[:fdt_offset]

    self._tools.WriteFile(image, uboot_data)
    return bl1, bl2, image, uboot_offset

  def ExynosFlashImage(self, flash_dest, flash_uboot, bl1, bl2, payload,
                       kernel):
    """Flash the image to SPI flash.

    This creates a special Flasher binary, with the image to be flashed as
    a payload. This is then sent to the board using the tegrarcm utility.

    Args:
      flash_dest: Destination for flasher, or None to not create a flasher.
          This is a dictionary of strings keyed by 'type', 'bus', and 'dev'.
          Valid options for 'type' are spi, sdmmc.
      flash_uboot: Full path to u-boot.bin to use for flasher.
      bl1: Full path to file containing BL1 (pre-boot).
      bl2: Full path to file containing BL2 (SPL).
      payload: Full path to payload.
      kernel: Kernel to send after the payload, or None.

    Returns:
      True if ok, False if failed.

    Raises:
      CmdError if a supported Exynos model is not detected in the device tree.
    """
    use_efs_memory = False
    tools = self._tools
    payload_bl1, payload_bl2, payload_image, spl_load_offset = (
        self._ExtractPayloadParts(payload, flash_dest is not None))
    bl2_handler = ExynosBl2(tools, self._out)
    if flash_dest:
      # If we don't have some bits, get them from the image
      if not flash_uboot or not os.path.exists(tools.Filename(flash_uboot)):
        self._out.Warning('Extracting U-Boot from payload')
        flash_uboot = payload_image
      if not bl1 or not os.path.exists(tools.Filename(bl1)):
        self._out.Warning('Extracting BL1 from payload')
        bl1 = payload_bl1
      if not bl2 or not os.path.exists(tools.Filename(bl2)):
        self._out.Warning('Extracting BL2 from payload')
        bl2 = payload_bl2
      else:
        # Update BL2 machine parameters, as the BL2 passed in may not be
        # updated. Also make sure it doesn't use early-firmware-selection
        # since our flasher needs to run from SDRAM.
        spl_load_size = os.stat(tools.Filename(bl2)).st_size
        bl2 = bl2_handler.Configure(self._fdt, spl_load_offset, spl_load_size,
                                    bl2, 'flasher', loose_check=True,
                                    use_efs_memory=False)
      # Set default values for Exynos targets.
      if flash_dest['bus'] is None:
        flash_dest['bus'] = 1
      if flash_dest['dev'] is None:
        flash_dest['dev'] = 0

      # Try to determine RO section size
      ro_size = None
      if flash_dest['type'] == 'sdmmc':
        try:
          ro_size = self._fdt.GetFlashPartSize('wp', 'ro')
        except (CmdError, ValueError):
          self._out.Warning('Unable to detect RO section size')

      image = self._PrepareFlasher(flash_uboot, payload, flash_dest, ro_size)
    else:
      bl1, bl2, image = payload_bl1, payload_bl2, payload_image

    vendor_id = 0x04e8
    product_id = 0x1234

    # Preserve dut_hub_sel state.
    preserved_dut_hub_sel = self.DutControl(['dut_hub_sel',]
                                            ).strip().split(':')[-1]
    required_dut_hub_sel = 'dut_sees_servo'
    args = ['warm_reset:on', 'fw_up:on', 'pwr_button:press', 'sleep:.2',
        'warm_reset:off']
    if preserved_dut_hub_sel != required_dut_hub_sel:
      # Need to set it to get the port properly powered up.
      args += ['dut_hub_sel:%s' % required_dut_hub_sel]
    if self._servo_port is not None:
      self._out.Progress('Reseting board via servo')
      self.DutControl(args)

    # If we have a kernel to write, create a new image with that added.
    if kernel:
      dl_image = os.path.join(self._tools.outdir, 'image-plus-kernel.bin')
      data = self._tools.ReadFile(image)

      # Pad the original payload out to the original length
      data += '\0' * (os.stat(payload).st_size - len(data))
      data += self._tools.ReadFile(kernel)
      self._tools.WriteFile(dl_image, data)
    else:
      # See which type of memory we should load U-Boot to
      used_size = self._fdt.GetFlashPartUsed('ro', 'boot')
      if self.use_efs and used_size:
        node = self._fdt.GetFlashNode('ro', 'boot')
        props = self._fdt.GetProp(node, 'type,efs', 'none')
        if props != 'none' and props[0] == 'blob':
          parts = props[1].split(',')
          use_efs_memory = 'ro-boot' in parts

      # Truncate the image to just the size actually used
      if use_efs_memory:
        dl_image = os.path.join(self._tools.outdir, 'image-used.bin')
        data = self._tools.ReadFile(image)
        self._tools.WriteFile(dl_image, data[:used_size])
        self._out.Warning('Truncating to used size %#x' % used_size)
      else:
        dl_image = image

    self._out.Progress('Uploading image')

    # This list tells us the memory region to use, the offset into that
    # region and the filename to upload.
    upload_list = [
        ['/iram', 'samsung,bl1-offset', bl1],
        ['/iram', 'samsung,bl2-offset', bl2],
        ['/memory', 'u-boot-offset', dl_image]
        ]

    try:
      for upto in range(len(upload_list)):
        item = upload_list[upto]
        if not self._WaitForUSBDevice('exynos', vendor_id, product_id, 4):
          if upto == 0:
            raise CmdError('Could not find Exynos board on USB port')
          raise CmdError("Stage '%s' did not complete" % item[1])
        self._out.Notice(item[2])

        if upto == 0:
          # The IROM needs roughly 200ms here to be ready for USB download
          time.sleep(.5)

        # Load U-Boot either to IRAM or SDRAM depending on EFS
        if upto == 2:
          addr = bl2_handler.GetUBootAddress(self._fdt, use_efs_memory)
        else:
          base = self._fdt.GetIntList(item[0], 'reg')[0]
          offset = self._fdt.GetIntList('/config', item[1])[0]
          addr = base + offset

        self._out.Progress("Uploading stage '%s' to %x" % (item[1], addr))
        args = ['-a', '%#x' % addr, '-f', item[2]]
        self._tools.Run('smdk-usbdl', args, sudo=True)

    finally:
      # Make sure that the power button is released and dut_sel_hub state is
      # restored, whatever happens
      args = ['fw_up:off', 'pwr_button:release']
      if preserved_dut_hub_sel != required_dut_hub_sel:
        args += ['dut_hub_sel:%s' % preserved_dut_hub_sel]
      self.DutControl(args)

    if flash_dest is None:
      self._out.Notice('Image downloaded - please see serial output '
                       'for progress.')
    return True

  def _GetDiskInfo(self, disk, item):
    """Returns information about a SCSI disk device.

    Args:
      disk: a block device name in sys/block, like '/sys/block/sdf'.
      item: the item of disk information that is required.

    Returns:
      The information obtained, as a string, or '[Unknown]' if not found
    """
    dev_path = os.path.join(disk, 'device')

    # Search upwards and through symlinks looking for the item.
    while os.path.isdir(dev_path) and dev_path != '/sys':
      fname = os.path.join(dev_path, item)
      if os.path.exists(fname):
        with open(fname, 'r') as fd:
          return fd.readline().rstrip()

      # Move up a level and follow any symlink.
      new_path = os.path.join(dev_path, '..')
      if os.path.islink(new_path):
        new_path = os.path.abspath(os.readlink(os.path.dirname(dev_path)))
      dev_path = new_path
    return '[Unknown]'

  def _GetDiskCapacity(self, device):
    """Returns the disk capacity in tenth of GB, or 0 if not known.

    Args:
      device: Device to check, like '/dev/sdf'.

    Returns:
      Capacity of device in GB, or 0 if not known.
    """
    re_capacity = re.compile('Disk %s: .* (\d+) bytes' % device)
    args = ['-l', device]
    stdout = self._tools.Run('fdisk', args, sudo=True)
    for line in stdout.splitlines():
      m = re_capacity.match(line)
      if m:
        return int(int(m.group(1)) / 1e8)
    return 0

  def _ListUsbDisks(self):
    """Return a list of available removable USB disks.

    Returns:
      List of USB devices, each element is itself a list containing:
        device ('/dev/sdx')
        manufacturer name
        product name
        capacity in tenth of GB (an integer)
    """
    disk_list = []
    for disk in glob.glob('/sys/block/sd*'):
      with open(disk + '/removable', 'r') as fd:
        if int(fd.readline()) == 1:
          device = '/dev/%s' % disk.split('/')[-1]
          manuf = self._GetDiskInfo(disk, 'manufacturer')
          product = self._GetDiskInfo(disk, 'product')
          capacity = self._GetDiskCapacity(device)
          if capacity:
            disk_list.append([device, manuf, product, capacity])
    return disk_list

  def WriteToSd(self, flash_dest, disk, uboot, payload):
    if flash_dest:
      # Set default values for sd.
      if flash_dest['bus'] is None:
        flash_dest['bus'] = 1
      if flash_dest['dev'] is None:
        flash_dest['dev'] = 0
      raw_image = self._PrepareFlasher(uboot, payload, flash_dest)
      bl1, bl2, _, spl_load_offset = self._ExtractPayloadParts(payload, True)
      spl_load_size = os.stat(raw_image).st_size

      bl2_handler = ExynosBl2(self._tools, self._out)
      bl2_file = bl2_handler.Configure(self._fdt, spl_load_offset,
                                       spl_load_size, bl2, 'flasher', True,
                                       use_efs_memory=False)
      data = self._tools.ReadFile(bl1) + self._tools.ReadFile(bl2_file)

      # Pad BL2 out to the required size. Its size could be either 14K or 30K
      # bytes, but the next object in the file needs to be aligned at an 8K
      # boundary. The BL1 size is also known to be 8K bytes, so the total BL1
      # + BL2 size needs to be aligned to 8K (0x2000) boundary.
      aligned_size = (len(data) + 0x1fff) & ~0x1fff
      pad_size =  aligned_size - len(data)
      data += '\0' * pad_size

      data += self._tools.ReadFile(raw_image)
      image = os.path.join(self._tools.outdir, 'flasher-with-bl.bin')
      self._tools.WriteFile(image, data)
      self._out.Progress('Writing flasher to %s' % disk)
    else:
      image = payload
      self._out.Progress('Writing image to %s' % disk)

    args = ['if=%s' % image, 'of=%s' % disk, 'bs=512', 'seek=1']
    self._tools.Run('dd', args, sudo=True)
    self._out.Progress('Syncing')
    self._tools.Run('sync', [], sudo=True)

  def SendToSdCard(self, dest, flash_dest, uboot, payload):
    """Write a flasher to an SD card.

    Args:
      dest: Destination in one of these forms:
          ':.' selects the only available device, fails if more than one option
          ':<device>' select deivce

          Examples:
            ':.'
            ':/dev/sdd'

      flash_dest: Destination for flasher, or None to not create a flasher:
          Valid options are spi, sdmmc.
      uboot: Full path to u-boot.bin.
      payload: Full path to payload.
    """
    disk = None

    # If no removable devices found - prompt user and wait for one to appear.
    disks = self._ListUsbDisks()
    try:
      spinner = '|/-\\'
      index = 0
      while not disks:
        self._out.ClearProgress()
        self._out.Progress('No removable devices found, plug something in %s '
                           % spinner[index], trailer='')
        index = (index + 1) % len(spinner)
        disks = self._ListUsbDisks()
        time.sleep(.2)
    except KeyboardInterrupt:
      raise CmdError("No removable device found, interrupted")

    if dest.startswith(':'):
      name = dest[1:]

      # A '.' just means to use the only available disk.
      if name == '.' and len(disks) == 1:
        disk = disks[0][0]
      for disk_info in disks:
        # Use the device name.
        if disk_info[0] == name:
          disk = disk_info[0]

    if disk:
      self.WriteToSd(flash_dest, disk, uboot, payload)
    else:
      msg = ["Please specify destination as '-w sd:<disk_description>'",]
      msg.append('   - <disk_description> can be either . for the only disk,')
      msg.append('     or the full device name, one of listed below:')
      # List available disks as a convenience.
      for disk in disks:
        msg.append('  %s - %s %.1f GB' % (
            disk[0],
            ' '.join(str(x) for x in disk[1:3]),
            disk[3] / 10.0))
      raise CmdError('\n'.join(msg))

  def Em100FlashImage(self, image_fname):
    """Send an image to an attached EM100 device.

    This is a Dediprog EM100 SPI flash emulation device. We set up servo2
    to do the SPI emulation, then write the image, then boot the board.
    All going well, this is enough to get U-Boot running.

    Args:
      image_fname: Filename of image to send
    """
    args = ['spi2_vref:off', 'spi2_buf_en:off', 'spi2_buf_on_flex_en:off']
    args.append('spi_hold:on')
    self.DutControl(args)

    # TODO(sjg@chromium.org): This is for link. We could make this
    # configurable from the fdt.
    args = ['-c', 'W25Q64CV', '-d', self._tools.Filename(image_fname), '-r']
    self._out.Progress('Writing image to em100')
    self._tools.Run('em100', args, sudo=True)

    if self._servo_port is not None:
      self._out.Progress('Resetting board via servo')
      args = ['cold_reset:on', 'sleep:.2', 'cold_reset:off', 'sleep:.5']
      args.extend(['pwr_button:press', 'sleep:.2', 'pwr_button:release'])
      self.DutControl(args)


def DoWriteFirmware(output, tools, fdt, flasher, file_list, image_fname,
                    bundle, update=True, verify=False, dest=None,
                    flasher_dest=None, kernel=None, bootstub=None,
                    servo='any', method='tegra'):
  """A simple function to write firmware to a device.

  This creates a WriteFirmware object and uses it to write the firmware image
  to the given destination device.

  Args:
    output: cros_output object to use.
    tools: Tools object to use.
    fdt: Fdt object to use as our device tree.
    flasher: U-Boot binary to use as the flasher.
    file_list: Dictionary containing files that we might need.
    image_fname: Filename of image to write.
    bundle: The bundle object which created the image.
    update: Use faster update algorithm rather then full device erase.
    verify: Verify the write by doing a readback and CRC.
    dest: Destination device to write firmware to (usb, sd).
    flasher_dest: a string, destination device for flasher to program payload
                  into. This string has the form <type>:[bus]:[dev], where
                  bus and dev are optional (and default to device and target
                  specific defaults when absent).
    kernel: Kernel file to write after U-Boot
    bootstub: string, file name of the boot stub, if present
    servo: Describes the servo unit to use: none=none; any=any; otherwise
           port number of servo to use.
  """
  write = WriteFirmware(tools, fdt, output, bundle, update, verify)
  write.SelectServo(servo)
  flash_dest = None
  if flasher_dest:
    # Parse flasher_dest and store into a dictionary.
    flash_dest_list = flasher_dest.split(":")
    flash_dest = {'type': flash_dest_list[0], 'bus': None, 'dev': None}
    if len(flash_dest_list) > 1:
      flash_dest['bus'] = flash_dest_list[1]
      if len(flash_dest_list) > 2:
        flash_dest['dev'] = flash_dest_list[2]
    write.text_base = bundle.CalcTextBase('flasher ', fdt, flasher)
  elif bootstub:
    write.text_base = bundle.CalcTextBase('bootstub ', fdt, bootstub)
  if dest == 'usb':
    try:
      write.DutControl(['cpu_uart_capture:on',])
      method = fdt.GetString('/chromeos-config', 'flash-method', method)
      if method == 'tegra':
        tools.CheckTool('tegrarcm')
        ok = write.NvidiaFlashImage(flash_dest, flasher, file_list['bct'],
            image_fname, bootstub)
      elif method == 'exynos':
        tools.CheckTool('lsusb', 'usbutils')
        tools.CheckTool('smdk-usbdl', 'smdk-dltool')
        ok = write.ExynosFlashImage(flash_dest, flasher,
            file_list['exynos-bl1'], file_list['exynos-bl2'], image_fname,
            kernel)
      else:
        raise CmdError("Unknown flash method '%s'" % method)

      if not ok:
        raise CmdError('Image upload failed - please check board connection')
      output.Progress('Image uploaded, waiting for completion')

      if flash_dest is not None and servo != 'none':
        write.WaitForCompletion()
      output.Progress('Done!')

    finally:
      write.DutControl(['cpu_uart_capture:off',])
  elif dest == 'em100':
    # crosbug.com/31625
    tools.CheckTool('em100')
    write.Em100FlashImage(image_fname)
  elif dest.startswith('sd'):
    write.SendToSdCard(dest[2:], flash_dest, flasher, image_fname)
  else:
    raise CmdError("Unknown destination device '%s'" % dest)
