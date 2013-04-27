# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import binascii
import glob
import os
import re
import struct
import time
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

  def _GetFlashScript(self, payload_size, boot_type, checksum, bus='0'):
    """Get the U-Boot boot command needed to flash U-Boot.

    We leave a marker in the string for the load address of the image,
    since this depends on the size of this script. This can be replaced by
    the caller provided that the marker length is unchanged.

    Args:
      payload_size: Size of payload in bytes.
      boot_type: The source for bootdevice (nand, sdmmc, or spi)
      checksum: The checksum of the payload (an integer)
      bus: The bus number

    Returns:
      A tuple containing:
        The script, as a string ready to use as a U-Boot boot command, with an
            embedded marker for the load address.
        The marker string, which the caller should replace with the correct
            load address as 8 hex digits, without changing its length.
    """
    replace_me = 'zsHEXYla'
    page_size = 4096
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
    if boot_type == 'nand':
      cmds.extend([
          'setenv _init   "echo Init NAND;  nand info"',
          'setenv _erase  "echo Erase NAND; nand erase            0 ${length}"',
          'setenv _write  "echo Write NAND; nand write ${address} 0 ${length}"',
          'setenv _read   "echo Read NAND;  nand read  ${address} 0 ${length}"',
      ])
    elif boot_type == 'sdmmc':
      cmds.extend([
          'setenv _init   "echo Init EMMC;  mmc rescan             0"',
          'setenv _erase  "echo Erase EMMC; "',
          'setenv _write  "echo Write EMMC; mmc open               0 1;' \
            '                               mmc write ${address}   0 ' \
            '${blocks};' \
            '                               mmc close              0 1"',
          'setenv _read   "echo Read EMMC;  mmc open               0 1;' \
            '                               mmc read ${address}    0 ' \
            '${blocks};' \
            '                               mmc close 0 1"',
      ])
    else:
      cmds.extend([
          'setenv _init   "echo Init SPI;   sf probe            %s"' % bus,
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
    return script, replace_me

  def _PrepareFlasher(self, uboot, payload, boot_type, bus):
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
      boot_type: the src for bootdevice (nand, sdmmc, or spi)

    Returns:
      Filename of the flasher binary created.
    """
    fdt = self._fdt.Copy(os.path.join(self._tools.outdir, 'flasher.dtb'))
    payload_data = self._tools.ReadFile(payload)

    # Make sure that the checksum is not negative
    checksum = binascii.crc32(payload_data) & 0xffffffff

    script, replace_me = self._GetFlashScript(len(payload_data), boot_type,
                                              checksum, bus)
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
    if len(replace_me) is not len(new_str):
      raise ValueError("Internal error: replacement string '%s' length does "
          "not match new string '%s'" % (replace_me, new_str))
    matches = len(re.findall(replace_me, fdt_data))
    if matches != 1:
      raise ValueError("Internal error: replacement string '%s' already "
          "exists in the fdt (%d matches)" % (replace_me, matches))
    fdt_data = re.sub(replace_me, new_str, fdt_data)

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
      flash_dest: Destination for flasher, or None to not create a flasher
          Valid options are spi, sdmmc
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
    # flash_dest selecting which bct to use. This is a bit backwards. For now
    # we go with the bct's idea.
    boot_type = filter(match.match, bct_dumped)
    boot_type = match.match(boot_type[0]).group('boot').lower()

    if flash_dest:
      image = self._PrepareFlasher(uboot, payload, boot_type, 0)
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
      match = re.search("^cpu_uart_stream:'(.*)'\n", stream)
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
      (bl1, bl2, image) where:
        bl1 is the filename of the extracted BL1
        bl2 is the filename of the extracted BL2
        image is the filename of the extracted U-Boot image
    """
    # Pull out the parts from the payload
    bl1 = os.path.join(self._tools.outdir, 'bl1.bin')
    bl2 = os.path.join(self._tools.outdir, 'bl2.bin')
    image = os.path.join(self._tools.outdir, 'u-boot-from-image.bin')
    data = self._tools.ReadFile(payload)

    # The BL1 is always 8KB - extract that part into a new file
    # TODO(sjg@chromium.org): Perhaps pick these up from the fdt?
    bl1_size = 0x2000
    self._tools.WriteFile(bl1, data[:bl1_size])

    # Try to detect the BL2 size. We look for 0xea000014 which is the
    # 'B reset' instruction at the start of U-Boot. When U-Boot is LZO
    # compressed, we look for a LZO magic instead.
    first_instr = struct.pack('<L', 0xea000014)
    lzo_magic = struct.pack('>B3s', 0x89, 'LZO')
    first_instr_offset = data.find(first_instr, bl1_size + 0x3800)
    lzo_magic_offset = data.find(lzo_magic, bl1_size + 0x3800)
    uboot_offset = min(first_instr_offset, lzo_magic_offset)
    if uboot_offset == -1:
      uboot_offset = max(first_instr_offset, lzo_magic_offset)
    if uboot_offset == -1:
      raise ValueError('Could not locate start of U-Boot')
    bl2_size = uboot_offset - bl1_size - 0x800  # 2KB gap after BL2

    # Sanity check: At present we only allow 14KB and 30KB for SPL
    allowed = [14, 30]
    if (bl2_size >> 10) not in allowed:
      raise ValueError('BL2 size is %dK - only %s supported' %
                       (bl2_size >> 10, ', '.join(
            [str(size) for size in allowed])))
    self._out.Notice('BL2 size is %dKB' % (bl2_size >> 10))

    # The BL2 (U-Boot SPL) follows BL1. After that there is a 2KB gap
    bl2_end = uboot_offset - 0x800
    self._tools.WriteFile(bl2, data[0x2000:bl2_end])

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
    return bl1, bl2, image

  def ExynosFlashImage(self, flash_dest, flash_uboot, bl1, bl2, payload,
                        kernel):
    """Flash the image to SPI flash.

    This creates a special Flasher binary, with the image to be flashed as
    a payload. This is then sent to the board using the tegrarcm utility.

    Args:
      flash_dest: Destination for flasher, or None to not create a flasher
          Valid options are spi, sdmmc.
      flash_uboot: Full path to u-boot.bin to use for flasher.
      bl1: Full path to file containing BL1 (pre-boot).
      bl2: Full path to file containing BL2 (SPL).
      payload: Full path to payload.
      kernel: Kernel to send after the payload, or None.

    Returns:
      True if ok, False if failed.
    """
    tools = self._tools
    payload_bl1, payload_bl2, payload_image = (
        self._ExtractPayloadParts(payload, flash_dest is not None))
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
      image = self._PrepareFlasher(flash_uboot, payload, flash_dest, '1:0')
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
      dl_image = image

    self._out.Progress('Uploading image')
    download_list = [
        # The numbers are the download addresses (in SRAM) for each piece
        # TODO(sjg@chromium.org): Perhaps pick these up from the fdt?
        ['bl1', 0x02021400, bl1],
        ['bl2', 0x02023400, bl2],
        ['u-boot', 0x43e00000, dl_image]
        ]
    try:
      for upto in range(len(download_list)):
        item = download_list[upto]
        if not self._WaitForUSBDevice('exynos', vendor_id, product_id, 4):
          if upto == 0:
            raise CmdError('Could not find Exynos board on USB port')
          raise CmdError("Stage '%s' did not complete" % item[0])
        self._out.Notice(item[2])
        self._out.Progress("Uploading stage '%s'" % item[0])

        if upto == 0:
          # The IROM needs roughly 200ms here to be ready for USB download
          time.sleep(.5)

        args = ['-a', '%#x' % item[1], '-f', item[2]]
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
      raw_image = self._PrepareFlasher(uboot, payload, flash_dest, '1:0')
      bl1, bl2, _ = self._ExtractPayloadParts(payload, True)
      spl_load_size = os.stat(raw_image).st_size
      bl2 = self._bundle.ConfigureExynosBl2(self._fdt, spl_load_size, bl2,
                                            'flasher')

      data = self._tools.ReadFile(bl1) + self._tools.ReadFile(bl2)

      # Pad BL2 out to the required size.
      # We require that it be 24KB, but data will only contain 8KB + 14KB.
      # Add the extra padding to bring it to 24KB.
      data += '\0' * (0x6000 - len(data))
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
                    flash_dest=None, kernel=None, bootstub=None, servo='any',
                    method='tegra'):
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
    flash_dest: Destination device for flasher to program payload into.
    kernel: Kernel file to write after U-Boot
    bootstub: string, file name of the boot stub, if present
    servo: Describes the servo unit to use: none=none; any=any; otherwise
           port number of servo to use.
  """
  write = WriteFirmware(tools, fdt, output, bundle, update, verify)
  write.SelectServo(servo)
  if flash_dest:
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
