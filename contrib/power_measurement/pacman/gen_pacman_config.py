#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2022 The ChromiumOS Authors.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utility to convert servod configs to pacman configs"""

import argparse
import importlib.util
import pathlib
import sys


def main():
    """main function"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--output", type=pathlib.Path)
    parser.add_argument(
        "input", help="Input servod python config file", type=pathlib.Path
    )

    args = parser.parse_args()

    spec = importlib.util.spec_from_file_location("config", args.input)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)

    with open(args.output, "w") as f:
        f.write("# Generated from servod board config\n")
        f.write("# addr:ch   name             nom    rsense\n")
        f.write("PACS = [\n")

        rails = []
        for (_, addr, name, nom, rsense, _, _) in config.inas:
            addrs = addr.split(":")
            if len(addrs) != 2:
                print(
                    f"{addr} does not match addr:channel format",
                    file=sys.stderr,
                )
                sys.exit(1)

            addr = addrs[0]
            channel = addrs[1]

            rails.append(name)
            f.write(
                (
                    f"    ('{addr}:{channel}', "
                    f"'{name.upper()}', {nom}, {rsense}),\n"
                )
            )

        f.write("]\n")

        # Servod config files don't contain this info, so fill in what we can.
        f.write("# rail             parent\n")
        f.write("RAILS = [\n")
        for rail in rails:
            f.write(f"    ('{rail.upper()}', 'NA'),\n")
        f.write("]\n")
        f.write("GPIOS = []\n")


if __name__ == "__main__":
    main()
