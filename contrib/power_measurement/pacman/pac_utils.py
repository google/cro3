# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import binascii
import signal
import time
import os
import importlib.util
import pandas
import pac19xx
from pyftdi.i2c import I2cController, I2cNackError


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


def reset_accumulator(device):
    """Command to reset PAC accumulators.

    Args:
        device: i2c port object.
    """
    device.write_to(pac19xx.REFRESH, 0)
    time.sleep(0.001)


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
    reg = device.read_from(lut[str(ch_num)], 7)
    count = device.read_from(pac19xx.ACC_COUNT, 4)
    count = int.from_bytes(count, byteorder='big', signed=False)
    if polarity == 'unipolar':
        reg = int.from_bytes(reg, byteorder='big', signed=False)
    else:
        reg = int.from_bytes(reg, byteorder='big', signed=True)
    return (reg, count)


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
    if polarity == 'unipolar':
        reg = b'\x00\x00'
    elif polarity == 'bipolar':
        reg = b'\x55\x55'
    else:
        raise ValueError('Unsupported polarity type ' + polarity)

    device.write_to(pac19xx.NEG_PWR_FSR, reg)
    print(f'Set \t{hex(device.address)} polarity to: {polarity}')


def load_config(config_file):
    """Loads the same config file used by servod into a pandas dataframe.

    Args:
        config File: PAC Address and sense resistor file.

    Returns:
        config: (Pandas Dataframe) config.
    """
    head_tail = os.path.split(config_file)
    module_name = head_tail[1]
    spec = importlib.util.spec_from_file_location(module_name, config_file)
    pacs = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pacs)

    config = pandas.DataFrame(pacs.INAS)
    config.columns = [
        'drv', 'addr', 'rail', 'nom', 'rsense', 'mux', 'is_calib'
    ]
    config['addr_pac'] = config.addr.apply(lambda x: x.split(':')[0])
    config['ch_num'] = config.addr.apply(lambda x: x.split(':')[1])
    return config


def load_gpio_config(gpio_config):
    """Loads a PAC address to GPIO rail name mapping csv file.

    Args:
        config File: (string) PAC Address and GPIO rail mapping.

    Returns:
        config: (Pandas Dataframe) config.
    """
    gpio_config = pandas.read_csv(gpio_config,
                                  skiprows=5,
                                  skipinitialspace=True)
    return gpio_config


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


def record(config_file,
           ftdi_url='ftdi:///',
           rail='all',
           record_length=360.0,
           voltage=True,
           current=True,
           power=True,
           polarity='bipolar'):
    """High level function to reset, log, then dump PAC power accumulations.

    Args:
        config_file: (string) Location of PAC Address/sense resitor .py file.
        ftdi_url: (string) ftdi_url.
        rail: (string, list of strings) name of rail to log. Must match.
          config rail name. will record all by default.
        record_length: (float) time in seconds to log.
        voltage: (boolean) log voltage.
        current: (boolean) log current.
        power: (boolean) log power.
        polarity: (string) ['unipolar', 'bipolar']

    Returns:
        time_log: (Pandas DataFrame) Time series log.
        acummulatorLog: (Pandas DataFrame) Accumulator totals.
    """

    # Init the bus.
    i2c = I2cController()
    i2c.configure(ftdi_url)
    # Load the config.
    config = load_config(config_file)
    # Filter the config to rows we care about.
    if 'all' not in rail:
        config = config[config['rail'].isin(rail)]

    # Clear all accumulators
    skip_pacs = []
    for pac_address, group in config.groupby('addr_pac'):

        try:
            device = i2c.get_port(int(pac_address, 16))
            set_polarity(device, polarity)
            disable_slow(device)
            reset_accumulator(device)
            time.sleep(0.001)
        except I2cNackError:
            # This happens on the DB PAC in Z states.
            print('Unable to reset PAC %s. Ignoring value' % pac_address)
            skip_pacs.append(pac_address)

    log = []
    # Register the signal handler for clean exits
    global terminate_signal
    terminate_signal = False
    signal.signal(signal.SIGINT, signal_handler)
    start_time = time.time()
    timeout = start_time + float(record_length)

    prev_accum_by_rail = {}
    prev_count_by_rail = {}

    while True:
        if time.time() > timeout:
            break
        if terminate_signal:
            break
        print('Logging: %.2f / %.2f s...' %
              (time.time() - start_time, float(record_length)),
              end='\r')

        # Group measurements by pac for speed.
        for pac_address, group in config.groupby('addr_pac'):
            if pac_address in skip_pacs:
                continue
            # Parse from the dataframe.
            device = i2c.get_port(int(pac_address, 16))
            # Setup any configuration changes here prior to refresh.
            device.write_to(pac19xx.REFRESH_V, 0)
            # Wait 1ms after REFRESH for registers to stablize.
            time.sleep(.001)
            # Log every rail on this pac we need to.
            for i, row in group.iterrows():
                try:
                    ch_num = row.ch_num
                    sense_r = float(row.rsense)

                    prev_accum = prev_accum_by_rail.get(row['rail'], 0)
                    prev_count = prev_count_by_rail.get(row['rail'], 0)

                    # Grab a log timestamp
                    tmp = {}
                    tmp['systime'] = time.time()
                    tmp['relativeTime'] = tmp['systime'] - start_time
                    tmp['rail'] = row['rail']

                    (accum, count) = dump_accumulator(device, ch_num, polarity)

                    tmp['rawAccumReg'] = accum
                    tmp['rawCount'] = count

                    prev_accum_by_rail[row['rail']] = accum
                    prev_count_by_rail[row['rail']] = count

                    accum = accum - prev_accum
                    count = count - prev_count

                    depth = {'unipolar': 2**30, 'bipolar': 2**29}
                    # Equation 3-8 Energy Calculation.
                    tmp['accumReg'] = accum
                    tmp['count'] = count

                    pwrFSR = 3.2 / sense_r
                    tmp['power'] = accum / (depth[polarity] * count) * pwrFSR

                    log.append(tmp)
                except I2cNackError:
                    print('NACK detected, continuing measurements')
                    time.sleep(.001)
                    continue
    time_log = pandas.DataFrame(log)
    time_log['power'] = time_log['power']
    pandas.options.display.float_format = '{:,.3f}'.format
    stats = time_log.groupby('rail').power.describe()

    accumulators = []
    # Dump the accumulator.
    for i, config_row in config.iterrows():
        if config_row.addr_pac in skip_pacs:
            continue
        accumulator = {}
        device = i2c.get_port(int(config_row['addr_pac'], 16))
        time.sleep(.001)
        accumulator['Rail'] = config_row['rail']
        (accum, count) = dump_accumulator(device, config_row.ch_num, polarity)
        accumulator['tAccum'] = time.time() - start_time
        accumulator['count'] = count
        depth = {'unipolar': 2**30, 'bipolar': 2**29}
        # Equation 3-8 Energy Calculation.
        accumulator['accumReg'] = accum
        accumulator['rSense'] = config_row.rsense
        pwrFSR = 3.2 / config_row.rsense
        accumulator['Average Power (w)'] = accum / (depth[polarity] *
                                                    count) * pwrFSR
        accumulators.append(accumulator)

    accumulatorLog = pandas.DataFrame(accumulators)
    print('Accumulator Power Measurements by Rail (W)')
    print(accumulatorLog.sort_values(by='Average Power (w)', ascending=False))

    return (time_log, accumulatorLog)


def query_all(config_file,
              gpio_config,
              ftdi_url='ftdi:///',
              polarity='bipolar'):
    """Preform a one time query of GPIOs, powers, currents, voltages.

    Args:
        config_file: (string) Location of PAC Address/sense resistor .py file.
        gpio_config: (string) Location of PAC Address Gpio rail mapping.
        ftdi_url: (string) URL of ftdi device.
        polarity: (string) 'bipolar' or 'unipolar'
    Returns:
        log: Pandas DataFrame with log voltage log.
    """
    # Init the bus.
    i2c = I2cController()
    i2c.configure(ftdi_url)
    # Load the config.
    config = load_config(config_file)
    # Load GPIO Config.
    gpio_config = load_gpio_config(gpio_config)

    # Ping all the PACs.
    skip_pacs = []
    for pac_address, group in config.groupby('addr_pac'):
        try:
            device = i2c.get_port(int(pac_address, 16))
            set_polarity(device, polarity)
            reset_accumulator(device)
            time.sleep(0.001)
        except I2cNackError:
            # This happens on the DB PAC in Z states
            print('Unable to reset PAC %s. Ignoring value' % pac_address)
            skip_pacs.append(pac_address)

    # Measure the GPIOs of all of the pacs
    gpio_log = []
    for pac_address, row in gpio_config.iterrows():
        tmp = {'Rail': row.Rail}
        if row.addr_pac in skip_pacs:
            continue
        # Parse from the dataframe.
        device = i2c.get_port(int(row.addr_pac, 16))
        if read_gpio(device):
            tmp['GPIO'] = 'High'
        else:
            tmp['GPIO'] = 'Low'
        gpio_log.append(tmp)
    gpio_log = pandas.DataFrame(gpio_log)
    print(gpio_log)

    # This just logs the instantaneous measurements once.
    log = []
    for i, config_row in config.iterrows():
        if config_row.addr_pac in skip_pacs:
            continue
        tmp = {}
        tmp['ic_name'] = config_row.drv
        tmp['ic_addr'] = config_row.addr.split(':')[0]
        tmp['ch_num'] = config_row.addr.split(':')[1]
        tmp['Rail'] = config_row.rail
        tmp['bus_volt'] = config_row.nom
        tmp['sense_r'] = config_row.rsense

        i2c = I2cController()
        i2c.configure(ftdi_url)

        device = i2c.get_port(int(tmp['ic_addr'], 16))
        # Setup any configuration changes here prior to refresh.
        device.write_to(pac19xx.REFRESH_V, 0)
        # Wait 1ms after REFRESH for registers to stablize.
        time.sleep(0.001)

        # Read voltage.
        tmp['act_volt'] = read_voltage(device, tmp['ch_num'], polarity)
        # Read power.
        tmp['power'] = read_power(device, tmp['sense_r'], tmp['ch_num'],
                                  polarity)
        # Read current.
        tmp['current'] = read_current(device, tmp['sense_r'], tmp['ch_num'],
                                      polarity)
        log.append(tmp)
    log = pandas.DataFrame(log)
    pandas.options.display.float_format = '{:,.3f}'.format
    print(log)
    return log
