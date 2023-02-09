#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool to provision, read and reset pacdebugger board info"""
import argparse
import random
import sys

import pacboard


def validate_default_device(device):
    """Ensures default device is only used when a single device is present"""
    if device == -1:
        (provisioned, unprovisioned) = pacboard.PacDebugger.get_boards()
        if len(provisioned) + len(unprovisioned) > 1:
            print(
                "Multiple devices exist, specify device with --device/-d",
                file=sys.stderr,
            )
            sys.exit(1)

        return 0

    return device


def dump(device):
    """Dumps the EEPROM contents of a PACDebugger"""
    device = validate_default_device(device)
    board = pacboard.PacDebugger(device)
    board.dump()


def list_boards():
    """Lists all attached pacdebuggers"""
    (provisioned, unprovisioned) = pacboard.PacDebugger.get_boards()
    if len(provisioned) > 0:
        print("Provisioned")
        print(f'Index {"Name":32} Serial')
        for (index, board) in provisioned:
            print(f"{index:<5} {board.name:32} {board.serial}")
        print("")

    if len(unprovisioned) > 0:
        print("Unprovisioned")
        print(f'Index {"Description":16}')
        for (index, desc) in unprovisioned:
            print(f"{index:<5} {desc:16}")


def provision(device, serial):
    """Provisions a pacdebugger with a serial number"""
    device = validate_default_device(device)
    board = pacboard.PacDebugger(device)

    if serial is None or serial == "":
        random.seed()
        # Use PACM prefix for manually provisioned devices
        serial = f"PACM{random.randrange(1, 2**32):#010}"

    board.serial = serial
    board.write_info()

    print(f"Provisioned with serial number {serial}")


def erase(device):
    """Erase the EEPROM of a PACDebugger"""
    device = validate_default_device(device)
    board = pacboard.PacDebugger(device)
    board.erase()


def unbrick(unbricker_url):
    """Unbricks a PACDebugger"""
    pacboard.PacDebugger.unbrick(unbricker_url)


def main():
    """Pactool main function"""
    parser = argparse.ArgumentParser()
    sub_parsers = parser.add_subparsers(help="sub-command -h for specific help")

    dump_parser = sub_parsers.add_parser("dump", help="Dump EEPROM contents")
    dump_parser.set_defaults(command="dump")
    dump_parser.add_argument(
        "--device", "-d", help="Index of device", type=int, default=-1
    )

    list_parser = sub_parsers.add_parser(
        "list", help="List currently connected devices"
    )
    list_parser.set_defaults(command="list")

    provision_parser = sub_parsers.add_parser(
        "provision", help="Provisions a device"
    )
    provision_parser.set_defaults(command="provision")
    provision_parser.add_argument(
        "--device", "-d", help="Index of device", type=int, default=-1
    )
    provision_parser.add_argument(
        "--serial",
        "-s",
        help="Serial number for device, \
        0 results in a randomly generated manually provisioned serial number",
        type=str,
        default=None,
    )

    erase_parser = sub_parsers.add_parser(
        "erase", help="Erases a provisioned device, unprovisioning it"
    )
    erase_parser.set_defaults(command="erase")
    erase_parser.add_argument(
        "--device", "-d", help="Index of device", type=int, default=-1
    )

    unbrick_parser = sub_parsers.add_parser(
        "unbrick",
        help="Unbricks a PACDebugger using a given FTDI USB<->SPI interface",
    )
    unbrick_parser.set_defaults(command="unbrick")
    unbrick_parser.add_argument(
        "unbricker_url", help="FTDI URL for SPI interface"
    )

    args = parser.parse_args()

    pacboard.PacDebugger.configure_custom_devices()

    if args.command == "dump":
        dump(args.device)
    elif args.command == "list":
        list_boards()
    elif args.command == "provision":
        provision(args.device, args.serial)
    elif args.command == "erase":
        erase(args.device)
    elif args.command == "unbrick":
        unbrick(args.unbricker_url)
    else:
        args.print_help()


if __name__ == "__main__":
    main()
