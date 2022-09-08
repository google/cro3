# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utilities for reading from PAC sensors"""

import binascii
import signal
import time

import pac19xx
import pandas
from pyftdi.i2c import I2cController
from pyftdi.i2c import I2cNackError

REFRESH_WAIT_TIME = 0.001


class PacBus:
    def __init__(self, i2c):
        """
        PacBus class holds initialized i2c port/pac objects, and can be
        used to refresh pac devices globally

        @param i2c: the i2c bus to use for the pac bus
        """
        self._i2c = i2c
        self._pac_devices = {}

    def add_device(self, addr):
        """read_from will initialize a new pac on the i2c bus

        @param addr: address of the new device to add

        @returns: the newly initialized port (or existing open port)
        """
        if addr not in self._pac_devices:
            self._pac_devices[addr] = self._i2c.get_port(addr)
        return self._pac_devices[addr]

    def get_device(self, addr):
        """read_from will initialize a new pac on the i2c bus

        @param addr: address of the new device to add
        """
        if addr not in self._pac_devices:
            raise KeyError("Pac device not initialized at this address")
        return self._pac_devices[addr]

    def refresh_all(self):
        """
        refresh_all writes to the "general call" for the pac
        devices, refreshing all accumulators synchronously
        """
        device = self._i2c.get_port(0x0)
        device.write_to(pac19xx.REFRESH_G, 0)
        time.sleep(REFRESH_WAIT_TIME)


def read_pac(device, reg, num_bytes):
    """Reads num_bytes from PAC I2C register using pyftdi driver.

    Args:
        device: (string) Serial port device name - ftdi:///?.
        reg: (int) Register to read.
        num_bytes: (int) Number of bytes to read.

    Returns:
        (string) Hex decoded as a string
    """
    pacval = device.read_from(reg, num_bytes)
    pacval = binascii.hexlify(pacval).decode()
    return pacval


def read_pac_int(device, reg, num_bytes):
    """Calls read_pac and returns the value as an int.

    Args:
        device: (string) Serial port device name - ftdi:///?.
        reg: (int) Register to read.
        num_bytes: (int) Number of bytes to read.

    Returns:
        (int) The value of read_pac converted to an int
    """
    pacval = read_pac(device, reg, num_bytes)
    return int(pacval, 16)


def read_voltage(device, ch_num=1, polarity='bipolar'):
    """Returns PAC voltage of given channel number.

    Args:
        device: i2c port object.
        ch_num: (int) PAC Channel number.
        polarity: (str) ['unipolar', or 'bipolar']

    Returns:
        act_volt: (float) Voltage.
    """
    # Read Voltage.
    act_volt = read_pac_int(device, pac19xx.VBUS1_AVG + int(ch_num), 2)
    # Convert to voltage.
    act_volt = act_volt * (pac19xx.FSV / pac19xx.V_POLAR[polarity])
    return float(act_volt)


def read_power(device, sense_resistance, ch_num=1, polarity='unipolar'):
    """Returns PAC power of given channel number.

    Args:
        device: i2c port object.
        sense_resistance: (float) sense resistance in Ohms.
        ch_num: (int) PAC Channel number.
        polarity: (str) ['unipolar', or 'bipolar']

    Returns:
        power: (float) Power in W.
    """
    # Read power
    power = read_pac_int(device, pac19xx.VPOWER1 + int(ch_num), 4)
    power_fsr = (pac19xx.FSR / float(sense_resistance)) * pac19xx.FSV
    p_prop = power / pac19xx.P_POLAR[polarity]
    power = power_fsr * p_prop * 0.25
    # *0.25 to shift right 2 places VPOWERn[29:0].
    return power


def read_current(device, sense_resistance, ch_num=1, polarity='unipolar'):
    """Returns PAC current of given channel number.

    Args:
        device: i2c port object.
        sense_resistance: (float) sense resistance in Ohms.
        ch_num: (int) PAC Channel number.
        polarity: (str) ['unipolar', or 'bipolar']

    Returns:
        current: (float) Current.
    """
    current = read_pac_int(device, pac19xx.VSENSE1_AVG + int(ch_num), 2)
    fsc = pac19xx.FSR / float(sense_resistance)
    current = (fsc / pac19xx.V_POLAR[polarity]) * current
    return float(current)


def read_gpio(device):
    """Returns GPIO status of PAC GPIO

    Args:
        device: i2c port object.

    Returns:
        gpioSetting: (bool) gpio.
    """
    # Read GPIO
    gpio = read_pac_int(device, pac19xx.SMBUS_SET, 1)
    return bool(gpio & (1 << 7))


def reset_accumulator(device, refresh_all=False):
    """Command to reset PAC accumulators.

    Args:
        device: i2c port object.
    """
    if refresh_all:
        device.refresh_all()
        return
    device.write_to(pac19xx.REFRESH, 0)
    time.sleep(REFRESH_WAIT_TIME)


def print_registers(device, pac_address):
    """Prints CTRL and SLOW registers.

    Args:
        device: i2c port object.
        pac_address: i2c hex address string.
    """

    # read back register and print value for debugging
    tmp = read_pac(device, pac19xx.CTRL, 2)
    print(f'{pac_address} register CTRL: \t\t0x{tmp}')
    tmp = read_pac(device, pac19xx.SLOW, 1)
    print(f'{pac_address} register SLOW: \t\t0x{tmp}')
    tmp = read_pac(device, pac19xx.CTRL_ACT, 2)
    print(f'{pac_address} register CTRL_ACT: \t0x{tmp}')
    tmp = read_pac(device, pac19xx.CTRL_LAT, 2)
    print(f'{pac_address} register CTRL_LAT: \t0x{tmp}')


def disable_slow(device):
    """Disable SLOW function of PAC accumulators.

    Changes SLOW pin to GPIO function.

    Args:
        device: i2c port object.
    """
    # Write CTRL register with 0x0500
    # #TODO consider changing to: read, bitwise AND, write
    # CTRL register defaults to 0x0700:
    # this sets bits[9:8] from 0b11 (SLOW) to 0b01 (GPIO in).
    # Alternate method is to keep register as SLOW but set FTDI GPIO Low
    device.write_to(pac19xx.CTRL, b'\x05\x00')

    # force refreshing the updated control register
    device.write_to(pac19xx.REFRESH, 0)


def enable_slow(device):
    """Disable SLOW function of PAC accumulators.

    Changes SLOW pin to GPIO function.

    Args:
        device: i2c port object.
    """
    # Write CTRL register with 0x0700
    # #TODO consider changing to: read, bitwise AND, write
    # returns CTRL register to default 0x0700:
    # this sets bits[9:8] to 0b11 (SLOW)
    # note this just enables SLOW control
    # #TODO more work needed for forcing FTDI GPIO High
    device.write_to(pac19xx.CTRL, b'\x07\x00')

    # force refreshing the updated control register
    device.write_to(pac19xx.REFRESH, 0)


def dump_accumulator(device, ch_num, polarity):
    """Command to acquire the voltage accumulator and counts for a PAC.

    Args:
        device: i2c port object.
        ch_num: channel to dump.
        polarity: str, unipolar/bipolar

    Returns:
        reg: (long) voltage accumulator register.
        count: (int) number of accumulations.
    """
    lut = {
        '0': pac19xx.VACC1,
        '1': pac19xx.VACC2,
        '2': pac19xx.VACC3,
        '3': pac19xx.VACC4
    }
    reg_bytes = device.read_from(lut[str(ch_num)], 7)
    count = device.read_from(pac19xx.ACC_COUNT, 4)
    count = int.from_bytes(count, byteorder='big', signed=False)
    if polarity == 'unipolar':
        reg = int.from_bytes(reg_bytes, byteorder='big', signed=False)
    else:
        reg = int.from_bytes(reg_bytes, byteorder='big', signed=True)
    return (reg, count)


def unpack_bytes_at(bytes_array, offset, length):
    """
    unpack_bytes_at extracts a subset of bytes from the bytes object and
    returns them.

    @param bytes: the input bytes_like object
    @param offset: the number of bytes to offset into the array
    @param length: the number of bytes the output
    """
    return bytes_array[offset:offset + length]


def dump_all_accumulators(device, polarity):
    """Command to acquire all voltage accumulator and counts for a PAC.

    Args:
        device: i2c port object
        polarity: str, unipolar/bipolar

    Returns:
        reg: (long) voltage accumulator register.
        count: (int) number of accumulations.
    """
    ACCUMULATOR_WIDTH = 7
    ACCUMULATOR_COUNT_WIDTH = 4

    all_bytes = device.read_from(pac19xx.ACC_COUNT, (ACCUMULATOR_WIDTH * 4) +
                                 ACCUMULATOR_COUNT_WIDTH)
    count_bytes = unpack_bytes_at(all_bytes, 0, ACCUMULATOR_COUNT_WIDTH)
    accum_bytes = unpack_bytes_at(all_bytes, ACCUMULATOR_COUNT_WIDTH,
                                  ACCUMULATOR_WIDTH * 4)
    accums = []
    for accum_idx in range(4):
        reg = 0
        sel_bytes = unpack_bytes_at(accum_bytes, accum_idx * ACCUMULATOR_WIDTH,
                                    ACCUMULATOR_WIDTH)
        if polarity == 'unipolar':
            reg = int.from_bytes(sel_bytes, byteorder='big', signed=False)
        else:
            reg = int.from_bytes(sel_bytes, byteorder='big', signed=True)
        accums.append(reg)
    count = int.from_bytes(all_bytes[:ACCUMULATOR_COUNT_WIDTH],
                           byteorder='big',
                           signed=False)
    return (accums, count)


def pac_info(ftdi_url):
    """Returns PAC debugging info

    Args:
        ftdi_url: (string) ftdi url.
    """

    # Init the bus
    i2c = I2cController()
    i2c.configure(ftdi_url)
    device = i2c.get_port(0x10)
    print(f'Device: \t{device}')
    tmp = read_pac(device, pac19xx.MANUFACTURER_ID, 1)
    print(f'PAC Mfg ID: \t0x{tmp}')
    tmp = read_pac(device, pac19xx.REVISION_ID, 1)
    print(f'PAC revision: \t0x{tmp}')
    tmp = read_pac(device, pac19xx.SMBUS_SET, 1)
    print(f'SMBus Set: \t0x{tmp}')
    tmp = read_pac(device, pac19xx.NEG_PWR_FSR, 1)
    print(f'NEG_PWR_FSR: \t0x{tmp}')
    tmp = read_pac(device, pac19xx.CTRL, 2)
    print(f'CTRL: \t\t0x{tmp}\n')


def set_polarity(device, polarity):
    """Sets the polarity of the given device"""
    if polarity == 'unipolar':
        reg = b'\x00\x00'
    elif polarity == 'bipolar':
        reg = b'\x55\x55'
    else:
        raise ValueError('Unsupported polarity type ' + polarity)

    device.write_to(pac19xx.NEG_PWR_FSR, reg)
    print(f'Set \t{hex(device.address)} polarity to: {polarity}')


terminate_signal = False


def signal_handler(signum, frame):
    """Define a signal handler for record so we can stop on CTRL-C.

    Autotest can call subprocess.kill which will make us stop waiting and
    dump the rest of the log.
    """

    print('Signal handler called with signal', signum)
    print('Dumping accumulators and generating reports.')
    global terminate_signal
    terminate_signal = True


def record(config,
           ftdi_url='ftdi:///',
           rails=['all'],
           record_length=360.0,
           voltage=True,
           current=True,
           power=True,
           polarity='bipolar',
           sample_time=5,
           refresh_all=True):
    """High level function to reset, log, then dump PAC power accumulations.

    Args:
        config: PacConfig
        ftdi_url: (string) ftdi_url.
        rail: (string, list of strings) name of rail to log. Must match.
          config rail name. will record all by default.
        record_length: (float) time in seconds to log.
        voltage: (boolean) log voltage.
        current: (boolean) log current.
        power: (boolean) log power.
        polarity: (string) ['unipolar', 'bipolar']
        sample_time: (float) time in seconds between log samples
        refresh_all: (boolean) refresh all pac devices synchronously

    Returns:
        time_log: (Pandas DataFrame) Time series log.
        acummulatorLog: (Pandas DataFrame) Accumulator totals.
    """

    # Init the bus.
    i2c = I2cController()
    i2c.configure(ftdi_url)
    accumulators = {}

    # Filter the config to rows we care about.
    allow_rails = set()
    if 'all' not in rails:
        for rail in rails:
            allow_rails.add(rail)

    # Clear all accumulators
    skip_pacs = set()

    pacbus = PacBus(i2c)
    for addr in config.pacs_by_addr:
        try:
            device = pacbus.add_device(addr)
            set_polarity(device, polarity)
            disable_slow(device)
            reset_accumulator(device)
        except I2cNackError:
            # This happens on the DB PAC in Z states.
            print(f'Unable to reset PAC {addr:#x}. Ignoring value')
            skip_pacs.add(addr)

    log = []
    # Register the signal handler for clean exits
    global terminate_signal
    terminate_signal = False
    signal.signal(signal.SIGINT, signal_handler)
    start_time = time.time()
    timeout = start_time + float(record_length)

    refresh_time = 0
    last_target_sample = time.time() - sample_time

    while True:
        if time.time() > timeout:
            break
        sleep = last_target_sample + sample_time - time.time()
        if sleep > 0:
            time.sleep(sleep)
        last_target_sample = last_target_sample + sample_time
        if terminate_signal:
            break
        print('Logging: %.2f / %.2f s...' %
              (time.time() - start_time, float(record_length)),
              end='\r')

        if refresh_all:
            pacbus.refresh_all()
            refresh_time = time.time()
        for addr, group in config.pacs_by_addr.items():
            if addr in skip_pacs:
                continue
            device = pacbus.get_device(addr)
            if not refresh_all:
                device.write_to(pac19xx.REFRESH_V, 0)
                refresh_time = time.time()
                time.sleep(REFRESH_WAIT_TIME)

            (accum, count) = dump_all_accumulators(device, polarity)
            # Log every rail on this pac we need to.
            for pac in group:
                if len(allow_rails) > 0 and pac.name not in allow_rails:
                    continue
                try:
                    ch_num = int(pac.channel)
                    sense_r = float(pac.rsense)

                    # Grab a log timestamp
                    tmp = {}
                    tmp['systime'] = refresh_time
                    tmp['relativeTime'] = refresh_time - start_time
                    tmp['rail'] = pac.name

                    depth = {'unipolar': 2**30, 'bipolar': 2**29}
                    # Equation 5-8 Energy Calculation.
                    tmp['accumReg'] = accum[ch_num]
                    tmp['count'] = count

                    pwrFSR = 3.2 / sense_r
                    tmp['power'] = (accum[ch_num] / (depth[polarity] * count) *
                                    pwrFSR)

                    if pac.name not in accumulators:
                        accumulators[pac.name] = {
                            'Rail': pac.name,
                            'rSense': pac.rsense,
                            'count': 0,
                            'accumReg': 0,
                            'Average Power (w)': 0
                        }

                    accumulators[
                        pac.name]['tAccum'] = refresh_time - start_time
                    accumulators[pac.name]['count'] += count

                    accumulators[pac.name]['accumReg'] += accum[ch_num]
                    new_weighting = count / accumulators[pac.name]['count']
                    old_weighting = 1 - new_weighting
                    accumulators[
                        pac.name]['Average Power (w)'] *= old_weighting
                    accumulators[pac.name]['Average Power (w)'] += (
                        tmp['power']) * new_weighting
                    log.append(tmp)
                except I2cNackError:
                    print('NACK detected, continuing measurements')
                    time.sleep(.001)
                    continue

    time_log = pandas.DataFrame(log)
    time_log['power'] = time_log['power']
    pandas.options.display.float_format = '{:,.3f}'.format
    stats = time_log.groupby('rail').power.describe()

    accumulatorLog = pandas.DataFrame(accumulators.values())
    print('Accumulator Power Measurements by Rail (W)')
    print(accumulatorLog.sort_values(by='Average Power (w)', ascending=False))

    return (time_log, accumulatorLog)


def query_all(config, ftdi_url='ftdi:///', polarity='bipolar'):
    """Preform a one time query of GPIOs, powers, currents, voltages.

    Args:
        config: PacConfig instance
        ftdi_url: (string) URL of ftdi device.
        polarity: (string) 'bipolar' or 'unipolar'

    Returns:
        log: Pandas DataFrame with log voltage log.
    """
    # Init the bus.
    i2c = I2cController()
    i2c.configure(ftdi_url)

    # Ping all the PACs.
    skip_pacs = set()
    for addr in config.pacs_by_addr:
        try:
            device = i2c.get_port(addr)
            set_polarity(device, polarity)
            reset_accumulator(device)
            time.sleep(0.001)
        except I2cNackError:
            # This happens on the DB PAC in Z states
            print(f'Unable to reset PAC {addr:#x}. Ignoring value')
            skip_pacs.add(addr)

    # Measure the GPIOs of all of the pacs
    gpio_log = []
    for gpio in config.gpios:
        tmp = {'Rail': gpio.rail}
        if gpio.addr in skip_pacs:
            continue
        # Parse from the dataframe.
        device = i2c.get_port(gpio.addr)
        if read_gpio(device):
            tmp['GPIO'] = 'High'
        else:
            tmp['GPIO'] = 'Low'
        gpio_log.append(tmp)

    gpio_log = pandas.DataFrame(gpio_log)
    print(gpio_log)

    # This just logs the instantaneous measurements once.
    log = []
    for pac in config.pacs:
        if pac.addr in skip_pacs:
            continue
        tmp = {}
        tmp['ic_addr'] = f'{pac.addr:#x}'
        tmp['ch_num'] = pac.channel
        tmp['Rail'] = pac.name
        tmp['bus_volt'] = pac.nom
        tmp['sense_r'] = pac.rsense

        i2c = I2cController()
        i2c.configure(ftdi_url)

        device = i2c.get_port(pac.addr)
        # Setup any configuration changes here prior to refresh.
        device.write_to(pac19xx.REFRESH_V, 0)
        # Wait 1ms after REFRESH for registers to stablize.
        time.sleep(0.001)

        # Read voltage.
        tmp['act_volt'] = read_voltage(device, pac.channel, polarity)
        # Read power.
        tmp['power'] = read_power(device, pac.rsense, pac.channel, polarity)
        # Read current.
        tmp['current'] = read_current(device, pac.rsense, pac.channel,
                                      polarity)
        log.append(tmp)

    log = pandas.DataFrame(log)
    pandas.options.display.float_format = '{:,.3f}'.format
    print(log)
    return log
