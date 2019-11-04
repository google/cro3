#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A script for kukui battery charger's efficiency/temperature measurement."""

from __future__ import print_function

import datetime
import subprocess
import sys
import time

import serial  # pylint: disable=import-error


def main():
    """
    this is main.
    """
    cmd = subprocess.check_output(['dut-control', 'ec_uart_pty'],
                                  encoding='utf-8')
    ec_pty = cmd.strip().split(':')[-1]
    ser = serial.Serial(ec_pty, 115200, timeout=3)
    ser.flush()
    ## Turn off AP before measuring.
    # ser.write(b'aps\n')
    time.sleep(0.1)
    # Turn off noisy EC console.
    ser.write(b'chan 0\n')
    f = open('output.csv', 'a')
    f.write('Time, USBC input voltage, Battery voltage, Battery current,'
            'Battery capacity, Efficiency, Temp\n')
    while True:
        try:
            while True:
                ser.write(b'battery\n')
                battery_voltage = None
                battery_current = None
                battery_capacity = None
                efficiency = None
                now = datetime.datetime.now()
                temp = None
                # Read battery infomation from EC console.
                for line in ser.readlines():
                    line = line.decode(encoding='utf-8', errors='ignore')
                    if 'V:' in line:
                        battery_voltage = line.split()[-2]
                        print('Time =  %s' % now)
                        print('Battery voltage = %s mV' % battery_voltage)
                    if 'I:' in line:
                        battery_current = line.split()[-2]
                        print('Battery current = %s mA' % battery_current)
                    if 'Charge:' in line:
                        battery_capacity = line.split()[-2]
                        print('Battery capacity = %s %%' % battery_capacity)

                # Exit if battery current is 0.
                if int(battery_current) == 0:
                    print('[Info.] Battery is full')
                    f.close()
                    sys.exit('[Info.] Goodbye!')

                # Read charger's temperature.
                ser.write(b'jc\n')
                line = ser.readline()
                line = ser.readline()
                temp = int(line.split()[-1])

                ## Set ADC and start ADC conversion of MT6370.
                # ser.write(b'i2cxfer w 0 0x34 0x21 0xc1\n')
                ## ADC needs 200ms to be stable.
                # time.sleep(0.2)
                ## Read the low-byte.
                # ser.write(b'i2cxfer r 0 0x34 0x4d\n')
                ## Output is in the 3rd line.
                # loop = 3
                # while loop > 0:
                #    line = ser.readline()
                #    loop -= 1
                #    time.sleep(0.1)
                # Temp = (ADC output * 2 ) - 40
                # print 'line = %s' % line
                # temp = (int(line.split()[-2], 16) * 2) - 40

                print('Temp of Charger = %d C' % temp)
                out = subprocess.check_output(['dut-control', 'ppvar_batt_mw',
                                               'ppvar_sys_mw',
                                               'ppvar_c0_vbus_mw',
                                               'ppvar_c0_vbus_mv'],
                                              encoding='utf-8')
                out_string = out.split('\n')

                # Read battery information from dut-control.
                if 'ppvar_batt_mw:' in out_string[0]:
                    P_BAT = abs(float(out_string[0].split(':', 1)[1]))
                    print('P_BAT = %s mW' % P_BAT)
                else:
                    print('can not find ppvar_batt_mw')

                if 'ppvar_c0_vbus_mv:' in out_string[1]:
                    V_USBC = float(out_string[1].split(':', 1)[1])
                    print('V_USBC = %s mV' % V_USBC)
                else:
                    print('can not find ppvar_c0_usbc_mv')

                if 'ppvar_c0_vbus_mw:' in out_string[2]:
                    P_USBC = float(out_string[2].split(':', 1)[1])
                    print('P_USBC = %s mW' % P_USBC)
                else:
                    print('can not find ppvar_c0_usbc_mw')

                if 'ppvar_sys_mw:' in out_string[3]:
                    P_SYS = float(out_string[3].split(':', 1)[1])
                    print('P_SYS = %s mW' % P_SYS)
                else:
                    print('can not find ppvar_sys_mw')

                # Exit if input power is 0.
                if P_USBC == 0:
                    print('[Error] Input power is 0, please check!')
                    sys.exit('[Error] Sorry, goodbye!')

                # Efficiency calculation.
                else:
                    efficiency = (P_BAT + P_SYS) / P_USBC * 100
                    print('The efficiency is: %.2f %%\n' % efficiency)
                    f.write('%s,%.1f,%s,%s,%s,%.2f%%,%d\n' % (
                        now, V_USBC, battery_voltage, battery_current,
                        battery_capacity, efficiency, temp,
                    ))
                    time.sleep(1)
            f.close()
        except IndexError:
            print('Unable to read')
        except KeyboardInterrupt:
            print('Exiting')
            sys.exit(0)


if __name__ == '__main__':
    main()
