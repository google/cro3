# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Module to deal with reading and writing pacdebugger board info"""

import pyftdi.eeprom
import pyftdi.ftdi
import pyftdi.misc
import pyftdi.spi


class BoardError(Exception):
    """Base exception class for errors related to the board"""

class InvalidDevice(BoardError):
    """Exception class for invalid devices"""
    def __str__(self):
        return 'Invaild Device'

class InvalidSerial(BoardError):
    """Exception class for an invalid serial number"""
    def __str__(self):
        return 'Invalid Serial'

class PacDebugger:
    """Board information for a pacdebugger"""
    UNPROVISIONED_VID = 0x0403
    UNPROVISIONED_PID = 0x6010

    PROVISIONED_VID = 0x18d1
    PROVISIONED_PID = 0x5211

    CONFIG_FILE = 'ftdi_config/ft2232h_template.ini'

    VID_PROPERTY = 'vendor_id'
    PID_PROPERTY = 'product_id'
    PRODUCT = 'PACDebuggerV1'

    EEPROM_SIZE = 128
    EEPROM_BYTE_WIDTH = 2

    # 100 KHz should be supported by everything
    UNBRICK_FREQ = 100000
    # Write enable command
    UNBRICK_WE_CMD = [0x98, 0x00]
    # Write disable command
    UNBRICK_WD_CMD = [0x90, 0x00]
    # Erase command
    UNBRICK_ERASE_CMD = 0xe0

    @staticmethod
    def get_boards():
        """Get provisioned and unprovisioned PACdebuggers"""
        provisioned = []
        unprovisioned = []
        devices = pyftdi.ftdi.Ftdi.find_all([
            (PacDebugger.UNPROVISIONED_VID, PacDebugger.UNPROVISIONED_PID),
            (PacDebugger.PROVISIONED_VID, PacDebugger.PROVISIONED_PID)
        ])

        index = 0
        for ((_, pid, _, _, _, _, desc), _) in devices:
            if pid == PacDebugger.PROVISIONED_PID:
                board = PacDebugger(index)
                board.read_info()
                provisioned.append((index, board))
            elif pid == PacDebugger.UNPROVISIONED_PID:
                unprovisioned.append((index, desc))
            index += 1

        return (provisioned, unprovisioned)

    @staticmethod
    def configure_custom_devices():
        """Allows our custom VID:PID to be recognized by the FTDI library"""
        pyftdi.misc.add_custom_devices(pyftdi.ftdi.Ftdi, [
            f'{PacDebugger.PROVISIONED_VID:#x}:{PacDebugger.PROVISIONED_PID:#x}'
        ], force_hex=True)


    @staticmethod
    def device_to_url(device):
        """Converts a device index into the corresponding device URL"""
        devices = pyftdi.ftdi.Ftdi.find_all([
            (PacDebugger.UNPROVISIONED_VID, PacDebugger.UNPROVISIONED_PID),
            (PacDebugger.PROVISIONED_VID, PacDebugger.PROVISIONED_PID)
        ])

        if device < 0 or device >= len(devices):
            raise InvalidDevice

        ((vid, pid, bus, addr, _, _, _), _) = devices[device]
        return f'ftdi://{vid:#x}:{pid:#x}:{bus:x}:{addr:x}/1'

    @staticmethod
    def url_by_serial(serial):
        """Returns the device URL of a pacdebugger by serial number"""
        return (f'ftdi://{PacDebugger.PROVISIONED_VID:#x}'
                f':{PacDebugger.PROVISIONED_PID:#x}:{serial}/1')

    @staticmethod
    def unbrick(unbricker_url):
        """Unbricks a PACDebugger using another FTDI USB<->SPI interface"""
        controller = pyftdi.spi.SpiController()
        controller.configure(unbricker_url)

        # Use first CS pin on the interface
        port = controller.get_port(cs=0, freq=PacDebugger.UNBRICK_FREQ)
        # EEPROM CS is active high
        port.force_select(level=False)

        # Send the write enable cmd
        port.force_select(level=True)
        port.write(PacDebugger.UNBRICK_WE_CMD, start=False, stop=False)
        port.force_select(level=False)

        erase_count = PacDebugger.EEPROM_SIZE // PacDebugger.EEPROM_BYTE_WIDTH
        for addr in range(0, erase_count):
            cmd1 = PacDebugger.UNBRICK_ERASE_CMD
            # Last addr bit doesn't fit in a single byte
            cmd1 |= addr >> 1
            cmd2 = (addr & 1) << 7

            port.force_select(level=True)
            port.write([cmd1, cmd2], start=False, stop=False)
            port.force_select(level=False)

        # Send write disable cmd
        port.force_select(level=True)
        port.write(PacDebugger.UNBRICK_WD_CMD, start=False, stop=False)
        port.force_select(level=False)


    def __init__(self, device):
        """Connects to a provisioned PACDebugger"""
        super().__init__()
        self.serial = ''
        self.name = ''

        ftdi_url = PacDebugger.device_to_url(device)
        self.eeprom = pyftdi.eeprom.FtdiEeprom()
        self.eeprom.open(ftdi_url, size=PacDebugger.EEPROM_SIZE)


    def read_info(self):
        """Reads the serial number and product name from the EEPROM"""
        self.serial = self.eeprom.serial
        self.name = self.eeprom.product


    def write_info(self):
        """Writes current info to board header"""
        # Use raw section because the ftdi library seems to have issues loading
        # certain values from the human readable portion of the config
        self.eeprom.load_config(open(PacDebugger.CONFIG_FILE), section='raw')

        self.eeprom.set_property(PacDebugger.VID_PROPERTY,
                                 PacDebugger.PROVISIONED_VID)
        self.eeprom.set_property(PacDebugger.PID_PROPERTY,
                                 PacDebugger.PROVISIONED_PID)

        self.eeprom.set_product_name(PacDebugger.PRODUCT)

        if not isinstance(self.serial, str) or self.serial == '':
            raise InvalidSerial
        self.eeprom.set_serial_number(self.serial)

        self.eeprom.commit(dry_run=False)


    def erase(self):
        """Erases the EEPROM"""
        self.eeprom.erase()
        self.eeprom.commit(dry_run=False, no_crc=True)


    def dump(self):
        """Dumps EEPROM contents as hex"""
        COLUMN_COUNT = 16
        rows = len(self.eeprom.data) // COLUMN_COUNT

        for j in range(0, rows):
            for i in range(0, 16):
                print(f'{self.eeprom.data[j * COLUMN_COUNT + i]:02x} ', end='')
            print('')
