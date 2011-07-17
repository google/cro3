# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import re
import time
import tools
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
  """
  def __init__(self, tools, fdt, output):
    """Set up a new WriteFirmware object.

    Args:
      tools: A tools library for us to use.
      fdt: An fdt which gives us some info that we need.
      output: An output object to use for printing progress and messages.
    """
    self._tools = tools
    self._fdt = fdt
    self._out = output
    self._text_base = self._fdt.GetInt('/chromeos-config/textbase');

  def _GetFlashScript(self, payload_size):
    """Get the U-Boot boot command needed to flash U-Boot.

    We leave a marker in the string for the load address of the image,
    since this depends on the size of this script. This can be replaced by
    the caller provided that the marker length is unchanged.

    Args:
      payload_size: Size of payload in bytes.

    Returns:
      A tuple containing:
        The script, as a string ready to use as a U-Boot boot command, with an
            embedded marker for the load address.
        The marker string, which the caller should replace with the correct
            load address as 8 hex digits, without changing its length.
    """
    replace_me = 'zsHEXYla'
    cmds = [
        'setenv address       0x%s' % replace_me,
        'setenv firmware_size %#x' % payload_size,
        'setenv length        %#x' % RoundUp(payload_size, 4096),
        'setenv _crc   "crc32 ${address} ${firmware_size}"',
        'setenv _init  "echo Initing SPI;  sf probe            0"',
        'setenv _erase "echo Erasing SPI;  sf erase            0 ${length}"',
        'setenv _write "echo Writing SPI;  sf write ${address} 0 ${length}"',
        'setenv _clear "echo Clearing RAM; mw.b     ${address} 0 ${length}"',
        'setenv _read  "echo Reading SPI;  sf read  ${address} 0 ${length}"',

        'echo Firmware loaded to ${address}, size ${firmware_size}, '
            'length ${length}',
        'run _crc',
        'run _init',
        'run _erase',
        'run _write',
        'run _clear',
        'run _read',
        'run _crc',
        'echo If the two CRCs above are equal, flash was successful.'
    ]
    script = '; '.join(cmds)
    return script, replace_me

  def PrepareFlasher(self, uboot, payload):
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

    Returns:
      Filename of the flasher binary created.
    """
    fdt = self._fdt.Copy(os.path.join(self._tools.outdir, 'flasher.dtb'))
    payload_size = os.stat(payload).st_size

    script, replace_me = self._GetFlashScript(payload_size)
    data = self._tools.ReadFile(uboot)
    fdt.PutString('/config/bootcmd', script)
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
    load_address = self._text_base + payload_offset,
    new_str = '%08x' % load_address
    if len(replace_me) is not len(new_str):
      raise ValueError("Internal error: replacement string '%s' length does "
          "not match new string '%s'" % (replace_me, new_str))
    if len(re.findall(replace_me, fdt_data)) != 1:
      raise ValueError("Internal error: replacement string '%s' already "
          "exists in the fdt (%d matches)" % (replace_me, matches))
    fdt_data = re.sub(replace_me, new_str, fdt_data)

    # Now put it together.
    data += fdt_data
    data += "\0" * (payload_offset - len(data))
    data += self._tools.ReadFile(payload)
    flasher = os.path.join(self._tools.outdir, 'flasher-for-image.bin')
    self._tools.WriteFile(flasher, data)

    # Tell the user about a few things.
    self._tools.OutputSize('U-Boot', uboot)
    self._tools.OutputSize('Payload', payload)
    self._tools.OutputSize('Flasher', flasher)
    return flasher

  def FlashImage(self, uboot, bct, payload):
    """Flash the image to SPI flash.

    This creates a special Flasher binary, with the image to be flashed as
    a payload. This is then sent to the board using the nvflash utility.

    Args:
      uboot: Full path to u-boot.bin.
      bct: Full path to BCT file (binary chip timings file for Nvidia SOCs).
      payload: Full path to payload.

    Returns:
      True if ok, False if failed.
    """
    flasher = self.PrepareFlasher(uboot, payload)

    self._out.Progress('Uploading flasher image')
    args = [
      'nvflash',
      '--bct', bct,
      '--setbct',
      '--bl',  flasher,
      '--go',
      '--setentry', "%#x" % self._text_base, "%#x" % self._text_base
    ]

    # TODO(sjg): Check for existence of board - but chroot has no lsusb!
    last_err = None
    for tries in range(10):
      try:
        # TODO(sjg): Make sudo an argument to Run()
        # TODO(sjg): Use Chromite library so we can monitor output
        self._tools.Run('sudo', args)
        self._out.Notice('Flasher downloaded - please see serial output '
            'for progress.')
        return True

      except CmdError as err:
        if not self._out.stdout_is_tty:
          return False

        # Only show the error output once unless it changes.
        err = str(err)
        if not 'USB device not found' in err:
          raise CmdError('nvflash failed: %s' % err)

        if err != last_err:
          self._out.Notice(err)
          last_err = err
          self._out.Progress('Please connect USB A-A cable and do a '
              'recovery-reset', True)
        time.sleep(1)

    return False
