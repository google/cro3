#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to go through roafteriniter logs and output candidates."""

from __future__ import print_function

import argparse
import collections
import sys


LogEntry = collections.namedtuple(
    "Logentry", ["varname", "typename", "fnname", "write_from_init"]
)


def get_parser():
    """Create and return an ArgumentParser instance."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fname",
        type=str,
        dest="fname",
        required=True,
        help="Path to rai_final",
    )
    return parser


def main(args):
    """main."""
    parser = get_parser()
    opts = parser.parse_args(args)

    contents = open(opts.fname).readlines()
    contents = sorted(set([i.strip() for i in contents]))

    field_value = lambda x: x.split(":")[1]

    all_entries = set()
    for line in contents:
        parts = line.strip().split()
        le = LogEntry(
            field_value(parts[0]),
            field_value(parts[1]),
            field_value(parts[2]),
            field_value(parts[3]),
        )
        all_entries.add(le)

    ok_vars, nk_vars = set(), set()
    for entry in all_entries:
        if entry.write_from_init == "OK":
            ok_vars.add((entry.varname, entry.typename))
        else:
            nk_vars.add((entry.varname, entry.typename))

    final = ok_vars - nk_vars
    for each in final:
        print(each)

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
