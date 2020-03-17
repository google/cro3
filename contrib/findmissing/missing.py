#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Find missing stable and backported mainline fix patches in chromeos.

TODO(hirthanan): rename functions to be representative of what code is doing
"""

from __future__ import print_function
import os
import time
import subprocess
import sys

import MySQLdb
import common


def get_status_from_cherrypicking_sha(sha):
    """Attempt to cherrypick sha into working directory to retrieve it's Status.

    The working directory and branch must be set when calling
    this function.

    Return Status Enum:
    MERGED if the patch has already been applied,
    OPEN if the patch is missing and applies cleanly,
    CONFLICT if the patch is missing and fails to apply.
    """
    ret = None

    cmd = 'git reset --hard HEAD'
    subprocess.run(cmd.split(' '), stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)

    try:
        result = subprocess.call(['git', 'cherry-pick', '-n', sha],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)

        if result:
            ret = common.Status.CONFLICT
        else:
            diff = subprocess.check_output(['git', 'diff', 'HEAD'])
            if diff:
                ret = common.Status.OPEN
            else:
                ret = common.Status.MERGED
    except subprocess.CalledProcessError:
        ret = common.Status.CONFLICT

    cmd = 'git reset --hard HEAD'
    subprocess.run(cmd.split(' '), stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)

    return ret


def upstream_sha_to_kernel_sha(db, chosen_table, branch, upstream_sha):
    """Retrieves chromeos/stable sha by indexing db.

    Returns sha or None if upstream sha doesn't exist downstream.
    """
    c = db.cursor()

    q = """SELECT sha
            FROM {chosen_table}
            WHERE upstream_sha = %s AND branch = %s""".format(chosen_table=chosen_table)
    c.execute(q, [upstream_sha, branch])
    row = c.fetchone()

    return row[0] if row else None


def get_current_time():
    """Returns DATETIME in specific time format required by SQL."""
    return time.strftime('%Y-%m-%d %H:%M:%S')


def insert_by_patch_id(db, branch, fixedby_upstream_sha):
    """Handles case where fixedby_upstream_sha may have changed in kernels.

    Returns True if successful patch_id insertion and False if patch_id not found.
    """
    c = db.cursor()

    # Commit sha may have been modified in cherry-pick, backport, etc.
    # Retrieve SHA in linux_chrome by patch-id by checking for fixedby_upstream_sha
    #  removes entries that are already tracked in chrome_fixes
    q = """SELECT lc.sha
            FROM linux_chrome AS lc
            JOIN linux_upstream AS lu
            ON lc.patch_id = lu.patch_id
            JOIN upstream_fixes as uf
            ON lc.upstream_sha = uf.upstream_sha
            WHERE uf.fixedby_upstream_sha = %s AND branch = %s
            AND (lc.sha, uf.fixedby_upstream_sha)
            NOT IN (
                SELECT kernel_sha, fixedby_upstream_sha
                FROM chrome_fixes
                WHERE branch = %s
            )"""
    c.execute(q, [fixedby_upstream_sha, branch, branch])
    chrome_shas = c.fetchall()

    # fixedby_upstream_sha has already been merged into linux_chrome
    #  chrome shas represent kernel sha for the upstream_sha fixedby_upstream_sha
    if chrome_shas:
        for chrome_sha in chrome_shas:
            entry_time = get_current_time()
            cl_status = common.Status.MERGED.name
            reason = 'Already merged into linux_chrome [upstream sha %s]' % fixedby_upstream_sha

            try:
                q = """INSERT INTO chrome_fixes
                        (kernel_sha, fixedby_upstream_sha,
                        branch, entry_time, close_time, status, reason)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                c.execute(q, [chrome_sha, fixedby_upstream_sha,
                                branch, entry_time, entry_time, cl_status, reason])
                db.commit()
            except MySQLdb.Error as e: # pylint: disable=no-member
                print('Failed to insert an already merged entry into chrome_fixes.', e)
        return True

    return False


def insert_fix_gerrit(db, chosen_table, chosen_fixes, branch, kernel_sha, fixedby_upstream_sha):
    """Inserts fix row by checking status of applying a fix change."""
    # Check if fix has been merged using it's patch-id since sha's might've changed
    success = insert_by_patch_id(db, branch, fixedby_upstream_sha)
    if success:
        return

    c = db.cursor()

    # Try applying patch and get status
    status = get_status_from_cherrypicking_sha(fixedby_upstream_sha)
    cl_status = status.name

    entry_time = get_current_time()

    close_time = fix_change_id = reason = None

    q = """INSERT INTO {chosen_fixes}
            (kernel_sha, fixedby_upstream_sha, branch,
            entry_time, close_time, fix_change_id, status, reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""".format(chosen_fixes=chosen_fixes)

    if status == common.Status.MERGED:
        # Create a row for the merged CL (we don't need to track this), but can be stored
        # to indicate that the changes of this patch are already merged
        # entry_time and close_time are the same since we weren't tracking when it was merged
        fixedby_kernel_sha = upstream_sha_to_kernel_sha(db, chosen_table,
                branch, fixedby_upstream_sha)
        print("""%s SHA [%s] already merged bugfix patch [kernel: %s] [upstream: %s]"""
                % (chosen_fixes, kernel_sha, fixedby_kernel_sha, fixedby_upstream_sha))

        reason = 'Patch applied to %s before this robot was run' % chosen_table
        close_time = entry_time

        # TODO(hirthanan): gerrit api call to retrieve change-id for merged commit
        fix_change_id = 1

    elif status == common.Status.OPEN:
        print("""TODO(hirthanan) create gerrit ticket for entry
                kernel_sha:fixedby_upstream_sha""", kernel_sha, fixedby_upstream_sha)

        fix_change_id = 0
    elif status == common.Status.CONFLICT:
        # Register conflict entry_time, do not create gerrit CL
        # Requires engineer to manually explore why CL doesn't apply cleanly
        pass

    try:
        c.execute(q, [kernel_sha, fixedby_upstream_sha,
                        branch, entry_time, close_time,
                        fix_change_id, cl_status, reason])
        print('Inserted row into fixes table', [chosen_fixes, kernel_sha, fixedby_upstream_sha,
                        branch, entry_time, entry_time, close_time,
                        fix_change_id, cl_status, reason])

    except MySQLdb.Error as e: # pylint: disable=no-member
        print('Error inserting fix CL into fixes table',
                [chosen_fixes, kernel_sha, fixedby_upstream_sha,
                        branch, entry_time, entry_time, close_time,
                        fix_change_id, cl_status, reason], e)


def missing_branch(db, branch, kernel_metadata):
    """Look for missing Fixup commits in provided chromeos or stable release."""
    c = db.cursor()
    branch_name = kernel_metadata.get_kernel_branch(branch)

    print('Checking branch %s' % branch_name)
    subprocess.check_output(['git', 'checkout', branch_name], stderr=subprocess.DEVNULL)

    # chosen_table is either linux_stable or linux_chrome
    chosen_table = kernel_metadata.path
    chosen_fixes = kernel_metadata.kernel_fixes_table

    # New rows to insert
    # Note: MySQLdb doesn't support inserting table names as parameters
    #   due to sql injection
    q = """SELECT chosen_table.sha, uf.fixedby_upstream_sha
            FROM {chosen_table} AS chosen_table
            JOIN upstream_fixes AS uf
            ON chosen_table.upstream_sha = uf.upstream_sha
            WHERE branch = %s
            AND (chosen_table.sha, uf.fixedby_upstream_sha)
            NOT IN (
                SELECT chosen_fixes.kernel_sha, chosen_fixes.fixedby_upstream_sha
                FROM {chosen_fixes} AS chosen_fixes
                WHERE branch = %s
            )""".format(chosen_table=chosen_table, chosen_fixes=chosen_fixes)
    try:
        c.execute(q, [branch, branch])
        print('Finding new rows to insert into fixes table',
                [chosen_table, chosen_fixes, branch])
    except MySQLdb.Error as e: # pylint: disable=no-member
        print('Error finding new rows to insert',
                [chosen_table, chosen_fixes, branch], e)

    for (kernel_sha, fixedby_upstream_sha) in c.fetchall():
        insert_fix_gerrit(db, chosen_table, chosen_fixes, branch, kernel_sha, fixedby_upstream_sha)

    # Old rows to Update
    q = """UPDATE {chosen_fixes} AS fixes
            JOIN linux_chrome AS lc
            ON fixes.fixedby_upstream_sha = lc.upstream_sha
            SET status = 'MERGED', close_time = %s, reason = %s
            WHERE fixes.branch = %s
            AND lc.branch = %s
            AND (fixes.status = 'OPEN' OR fixes.status = 'CONFLICT')
            """.format(chosen_fixes=chosen_fixes)

    close_time = get_current_time()
    reason = 'Patch has been applied to linux_chrome'

    try:
        c.execute(q, [close_time, reason, branch, branch])
        print('Updating rows that have been merged into linux_chrome on table/branch',
                [chosen_fixes, branch])
    except MySQLdb.Error as e: # pylint: disable=no-member
        print('Error updating fixes table for merged commits',
                [chosen_fixes, close_time, reason, branch, branch], e)

    db.commit()


def missing_helper(db, kernel_metadata):
    """Helper to find missing patches in the stable and chromeos releases."""
    if len(sys.argv) > 1:
        branches = sys.argv[1:]
    else:
        branches = kernel_metadata.branches

    os.chdir(common.get_kernel_absolute_path(kernel_metadata.path))

    for b in branches:
        missing_branch(db, b, kernel_metadata)

    os.chdir(common.WORKDIR)


def missing(db):
    """Finds missing patches in stable and chromeos releases."""
    print('--Missing patches from baseline -> stable.--')
    kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_stable)
    missing_helper(db, kernel_metadata)

    print('--Missing patches from baseline -> chromeos.--')
    kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_chrome)
    missing_helper(db, kernel_metadata)


if __name__ == '__main__':
    cloudsql_db = MySQLdb.Connect(user='linux_patches_robot', host='127.0.0.1', db='linuxdb')
    missing(cloudsql_db)
    cloudsql_db.close()
