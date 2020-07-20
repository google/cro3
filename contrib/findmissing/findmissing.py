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
import sys
import main


def findmissing():
    """Parses command line args and calls correct function for findmissing.

    To execute abandon/restore commands i.e:
    ./findmissing abandon stable_fixes <kernel_sha> <fixedby_upstream_sha> reason
    """
    abandon_restore_function_map = {'abandon': main.abandon_fix_cl,
                                    'restore': main.restore_fix_cl,
                                    'status': main.status_fix_cl}
    parser = argparse.ArgumentParser(description='Local functions to update database')
    parser.add_argument('command', type=str, choices=tuple(abandon_restore_function_map.keys()),
                        help='Function to either abandon/restore changes.')
    parser.add_argument('fix', type=str, choices=('stable', 'chrome'),
                        help='Table that contains primary key you want to update.')
    parser.add_argument('-f', '--force', action='store_true',
        help='Force action if only one SHA provided and more than one database entry is affected.')
    parser.add_argument('-r', '--reason', required='status' not in sys.argv, type=str,
                        help='Reason for performing action.')
    parser.add_argument('sha', type=str, nargs='+',
                        help='To-be-fixed and/or fixing SHA for row you want to update.')
    args = parser.parse_args()

    if args.command != 'status' and len(args.sha) > 2:
        parser.error('Must specify one or two SHAs.')

    fixes_table = args.fix + '_fixes'
    abandon_restore_function_map[args.command](fixes_table, args.sha, args.reason, args.force)


if __name__ == '__main__':
    findmissing()
