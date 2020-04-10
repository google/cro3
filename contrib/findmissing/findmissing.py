#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Main interface for engineers to abandon/restore CL's viewed on Data Studio.

Before running this script, make sure you have been added to chromeos-missing-patches GCP project.

Prerequisites to execute this script locally (PERFORM ONCE):
>> ./scripts/local/local_database_setup.py

All abandon/restore findmissing commands must be run in this directory's
    virtual env (source env/bin/activate) before running any commands
"""

from __future__ import print_function

import argparse
import main


def findmissing():
    """Parses command line args and calls correct function for findmissing.

    To execute abandon/restore commands i.e:
    ./findmissing abandon stable_fixes <kernel_sha> <fixedby_upstream_sha> reason
    """
    abandon_restore_function_map = {'abandon': main.abandon_fix_cl,
                                    'restore': main.restore_fix_cl}
    parser = argparse.ArgumentParser(description='Local functions to update database')
    parser.add_argument('command', type=str, choices=tuple(abandon_restore_function_map.keys()),
                        help='Function to either abandon/restore changes.')
    parser.add_argument('fix', type=str, choices=('stable', 'chrome'),
                        help='Table that contains primary key you want to update.')
    parser.add_argument('patch', type=str,
                        help='kernel_sha of row you want to update.')
    parser.add_argument('fixed_by', type=str,
                        help='fixedby_upstream_sha of row you want to update.')
    parser.add_argument('reason', type=str, help='Reason for performing action.')
    args = parser.parse_args()

    fixes_table = args.fix + '_fixes'
    abandon_restore_function_map[args.command](fixes_table, args.patch,
                                                args.fixed_by, args.reason)



if __name__ == '__main__':
    findmissing()
