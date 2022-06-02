#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2022 The ChromiumOS Authors.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Utility to convert pacman configs to servod xml configs"""

import argparse
import pathlib

import pacconfig


def write_servod_config(config, outpath):
    """Converts pacman config to servod config"""
    f = open(outpath, 'w')

    f.write('# Generated from pacman board config\n')
    f.write("config_type='servod'\n\n")
    f.write('inas = [\n')
    for pac in config.pacs:
        f.write((f"    ('pac1954', '{pac.addr:#x}:{pac.channel}', "
            f"'{pac.name.lower()}', {pac.nom}, {pac.rsense}, 'rem', True),\n"))

    f.write(']')
    f.close()


def main():
    """main function"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-o',
        '--output',
        type=pathlib.Path
    )
    parser.add_argument(
        'input',
        type=pathlib.Path
    )

    args = parser.parse_args()

    config = pacconfig.PacConfig(args.input)
    write_servod_config(config, args.output)

if __name__ == '__main__':
    main()
