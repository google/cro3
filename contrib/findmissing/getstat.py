#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# pylint: pylint: disable=filter-builtin-not-iterating

"""Utility command to get statistics."""

import argparse

import common
import util


@util.cloud_sql_proxy_decorator
@util.preliminary_check_decorator(False)
def get_stat(list_all=False, branch=None, chromium=False, conflicts=False):
    """Report statistics for list of patches in given repository and branch"""
    if list_all:
        metadata = [
            common.get_kernel_metadata(common.Kernel.linux_chrome),
            common.get_kernel_metadata(common.Kernel.linux_stable),
        ]

        status = ["CONFLICT", "OPEN"]
    else:
        if chromium:
            metadata = [common.get_kernel_metadata(common.Kernel.linux_chrome)]
        else:
            metadata = [common.get_kernel_metadata(common.Kernel.linux_stable)]

        if conflicts:
            status = ["CONFLICT"]
        else:
            status = ["OPEN"]

    with common.connect_db() as db, db.cursor() as c:
        for m in metadata:
            fixes_table = m.kernel_fixes_table

            print("%s:" % fixes_table)

            if branch:
                branches = [branch]
            else:
                branches = m.branches

            q = f"""SELECT COUNT(*)
                    FROM {fixes_table}
                    WHERE status = %s
                    AND branch = %s"""

            for s in status:
                print("  %s:" % s)

                if list_all:
                    total = 0

                for b in branches:
                    c.execute(q, [s, b])
                    n = c.fetchone()[0]
                    print("    %s: %d" % (m.get_kernel_branch(b), n))

                    if list_all:
                        total += n

                if list_all:
                    print("  Total: %d\n" % total)


def main():
    """Parses command line args and calls the actual function with parsed parameters

    To execute:
    ./getstat [-a] [-b branch] [-c] [-C]
    """
    metadata = common.get_kernel_metadata(common.Kernel.linux_stable)
    parser = argparse.ArgumentParser(
        description="Local functions to retrieve data from database"
    )
    parser.add_argument(
        "-a",
        "--list_all",
        action="store_true",
        help="List all combinations",
    )
    parser.add_argument(
        "-b",
        "--branch",
        type=str,
        choices=metadata.branches,
        help="Branch to check",
    )
    parser.add_argument(
        "-C",
        "--chromium",
        action="store_true",
        help="Look for pending chromium patches",
    )
    parser.add_argument(
        "-c",
        "--conflicts",
        action="store_true",
        help="Check for conflicting patches",
    )
    args = vars(parser.parse_args())

    get_stat(**args)


if __name__ == "__main__":
    main()
