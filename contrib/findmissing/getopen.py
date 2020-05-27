#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# pylint: pylint: disable=filter-builtin-not-iterating

"""Utility command for engineers to get list of unresolved fixes

This command can be used by engineers to get a list of unresolved
chromium or stable fixes. Users can ask for unresolved fixes with open CLs
or for unresolved fixes with conflicts.

Before running this script, make sure you have been added to the
chromeos-missing-patches GCP project.

Prerequisites to execute this script locally (RUN ONCE):
>> ./scripts/local/local_database_setup.py

All locally executed commands must be run in this directory's
virtual env (source env/bin/activate) before running any commands.
The associated shell script enables this environment.
"""

from __future__ import print_function

import argparse
import re
import MySQLdb

import common
import git_interface
import missing
import synchronize
import util


# extract_numerics matches numeric parts of a Linux version as separate elements
# For example, "v5.4" matches "5" and "4", and "v5.4.12" matches "5", "4", and "12"
extract_numerics = re.compile(r'(?:v)?([0-9]+)\.([0-9]+)(?:\.([0-9]+))?\s*')

def branch_order(branch):
    """Calculate numeric order of tag or branch.

    A branch with higher version number will return a larger number.
    Ignores release candidates. For example, v5.7-rc1 will return the same
    number as v5.7-rc2.

    Returns 0 if the kernel version can not be extracted.
    """

    m = extract_numerics.match(branch)
    if m:
        major = int(m.group(1))
        minor1 = int(m.group(2))
        minor2 = int(m.group(3)) if m.group(3) else 0
        return major * 10000 + minor1 * 100 + minor2
    return 0


# version_baseline matches the numeric part of the major Linux version as a string
# For example, "v5.4.15" and "v5.4-rc3" both match "5.4"
version_baseline = re.compile(r'(?:v)?([0-9]+\.[0-9]+(?:\.[0-9]+)?)\s*')

def version_list(branches, start, end):
    """Return list of stable release branches between 'start' and 'end'.

    'branches' is the sorted list of branches to match.
    'start' and 'end' can be any valid kernel version or tag.
    If 'start' is empty or invalid, start list with first supported
    stable branch.
    If 'end' is empty or invalid, end list with last supported stable
    branch.
    """

    offset = 0

    if start:
        # Extract numeric part of 'start'
        start_match = version_baseline.match(start)
        start = start_match.group(1) if start_match else None
    if not start:
        start = branches[0]
    if end:
        end_match = version_baseline.match(end)
        end = end_match.group(1) if end_match else None
    if not end:
        end = branches[-1]
        # If we have no 'end', also match the last branch
        offset = 1

    min_order = branch_order(start)
    max_order = branch_order(end) + offset
    return list(filter(lambda x: branch_order(x) >= min_order and branch_order(x) < max_order,
                       branches))


def mysort(elem):
    """Function to sort branches based on version number"""
    _, branch = elem
    return branch_order(branch)


def report_integration_status_sha(repository, merge_base, branch_name, sha):
    """Report integration status for given repository, branch, and sha"""

    if repository is common.STABLE_PATH:
        # It is possible that the patch has not yet been applied but is queued
        # in a stable release candidate. Try to find it there as well. We use
        # this information to override the final status if appropriate.
        rc_metadata = common.get_kernel_metadata(common.Kernel.linux_stable_rc)
        rc_status = git_interface.get_cherrypick_status(rc_metadata.path, merge_base,
                                                        branch_name, sha)
    else:
        rc_status = common.Status.OPEN

    status = git_interface.get_cherrypick_status(repository, merge_base, branch_name, sha)
    if status == common.Status.CONFLICT:
        disposition = ' (queued)' if rc_status == common.Status.MERGED \
                                  else ' (conflicts - backport needed)'
    elif status == common.Status.MERGED:
        disposition = ' (already applied)'
    else:
        disposition = ' (queued)' if rc_status == common.Status.MERGED else ''

    print('      %s%s' % (branch_name, disposition))

def report_integration_status_branch(db, metadata, handled_shas, branch, conflicts):
    """Report integration status for list of open patches in given repository and branch"""

    if metadata.kernel_fixes_table == 'stable_fixes':
        table = 'linux_stable'
        branch_name_pattern = 'linux-%s.y'
    else:
        table = 'linux_chrome'
        branch_name_pattern = 'chromeos-%s'

    c = db.cursor()

    status = 'CONFLICT' if conflicts else 'OPEN'

    # Walk through all fixes table entries with given status
    q = """SELECT ct.fixedby_upstream_sha, lu.description, t.upstream_sha, t.description
            FROM {chosen_table} AS ct
            JOIN linux_upstream AS lu
            ON ct.fixedby_upstream_sha = lu.sha
            JOIN {table} as t
            ON ct.kernel_sha = t.sha
            WHERE ct.status = %s
            AND ct.branch = %s""".format(chosen_table=metadata.kernel_fixes_table, table=table)
    c.execute(q, [status, branch])
    for fixedby_sha, fixedby_description, fixes_sha, fixes_description in c.fetchall():
        # If we already handled a SHA while running this command while examining
        # another branch, we don't need to handle it again.
        if fixedby_sha in handled_shas:
            continue
        handled_shas += [fixedby_sha]

        print('Upstream commit %s ("%s")' % (fixedby_sha, fixedby_description))
        integrated = git_interface.get_integrated_tag(fixedby_sha)
        end = integrated
        if not integrated:
            integrated = 'ToT'
        print('  upstream: %s' % integrated)
        print('    Fixes: %s ("%s")' % (fixes_sha, fixes_description))

        q = """SELECT sha, branch
               FROM {table}
               WHERE upstream_sha = %s""".format(table=table)
        c.execute(q, [fixes_sha])
        fix_rows = sorted(c.fetchall(), key=mysort)
        affected_branches = []
        for fix_sha, fix_branch in fix_rows:
            if fix_branch in metadata.branches:
                affected_branches += [fix_branch]
                branch_name = branch_name_pattern % fix_branch
                print('      in %s: %s' % (branch_name, fix_sha))

        start = git_interface.get_integrated_tag(fixes_sha)
        if start:
            print('      upstream: %s' % git_interface.get_integrated_tag(fixes_sha))

        affected_branches += version_list(metadata.branches, start, end)
        affected_branches = sorted(list(set(affected_branches)), key=branch_order)
        if affected_branches:
            print('    Affected branches:')
            for affected_branch in affected_branches:
                merge_base = 'v%s' % affected_branch
                branch_name = branch_name_pattern % affected_branch
                report_integration_status_sha(metadata.path, merge_base, branch_name, fixedby_sha)

        # Check if this commit has been fixed as well and, if so, report it
        subsequent_fixes = missing.get_subsequent_fixes(db, fixedby_sha)
        # remove initial fix
        subsequent_fixes.pop(0)
        if subsequent_fixes:
            subsequent_fixes = ["\'" + sha + "\'" for sha in subsequent_fixes]
            parsed_fixes = ', '.join(subsequent_fixes)
            # format query here since we are inserting n values
            q = """SELECT sha, description
                   FROM linux_upstream
                   WHERE sha in ({})
                   ORDER BY FIELD(sha, {})""".format(parsed_fixes, parsed_fixes)
            c.execute(q)
            fixes = c.fetchall()
            print('    Fixed by:')
            for fix in fixes:
                print('      %s ("%s")' % fix)


@util.cloud_sql_proxy_decorator
@util.preliminary_check_decorator(False)
def report_integration_status(branch, conflicts, is_chromium):
    """Report list of open patches"""

    handled_shas = []

    if is_chromium:
        metadata = common.get_kernel_metadata(common.Kernel.linux_chrome)
    else:
        metadata = common.get_kernel_metadata(common.Kernel.linux_stable)

    synchronize.synchronize_repositories(True)

    db = MySQLdb.Connect(user='linux_patches_robot', host='127.0.0.1', db='linuxdb')

    if branch:
        report_integration_status_branch(db, metadata, handled_shas, branch, conflicts)
    else:
        for b in metadata.branches:
            print('\nBranch: linux-%s.y\n' % b)
            report_integration_status_branch(db, metadata, handled_shas, b, conflicts)

    db.close()


def report_integration_status_parse():
    """Parses command line args and calls the actual function with parsed parameters

    To execute:
    ./getopen [-b branch] [-c] [-C]
    """

    metadata = common.get_kernel_metadata(common.Kernel.linux_stable)
    parser = argparse.ArgumentParser(description='Local functions to retrieve data from database')
    parser.add_argument('-b', '--branch', type=str, choices=metadata.branches,
                        help='Branch to check')
    parser.add_argument('-C', '--chromium', action='store_true',
                        help='Look for pending chromium patches')
    parser.add_argument('-c', '--conflicts', action='store_true',
                        help='Check for conflicting patches')
    args = parser.parse_args()

    report_integration_status(args.branch, args.conflicts, args.chromium)

if __name__ == '__main__':
    report_integration_status_parse()
