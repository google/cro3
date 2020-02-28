#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Find missing stable and backported mainline fix patches in chromeos."""

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


def upstream_sha_to_kernel_sha(db, linux_table, branch, upstream_sha):
    """Retrieves chromeos/stable sha by indexing db.

    Returns sha or None if upstream sha doesn't exist downstream.
    """
    c = db.cursor()

    q = """SELECT sha
            FROM %s
            WHERE upstream_sha = %s AND branch = %s"""
    c.execute(q, [linux_table, upstream_sha, branch])
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
    q = """SELECT linux_chrome.sha
            FROM linux_chrome AS lc
            JOIN linux_upstream_commits as LUC
            ON lc.patch_id = luc.patch_id
            WHERE linux_chrome.upstream_sha = %s AND branch = %s"""
    c.execute(q, [fixedby_upstream_sha, branch])
    sha_row = c.fetchone()

    if sha_row:
        entry_time = get_current_time()
        cl_status = common.Status.MERGED.name
        reason = 'Found bugfix patch in linux_chrome for sha %s' % fixedby_upstream_sha

        try:
            q = """INSERT INTO chrome_fixes
                    (kernel_sha, fixedby_upstream_sha, branch, entry_time, close_time, status, reason)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)"""
            c.execute(q, [sha_row[0], fixedby_upstream_sha,
                            branch, entry_time, entry_time, cl_status, reason])
            db.commit()
            return True
        except MySQLdb.Error as e: # pylint: disable=no-member
            print('Failed to insert an already merged entry into chrome_fixes.', e)

    return False


def insert_fixes_gerrit(db, fixes_table, branch, kernel_sha, fixedby_upstream_sha):
    """Inserts fixes_table rows by checking status of applying a fix change."""
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

    q = """INSERT INTO %s
            (kernel_sha, fixedby_upstream_sha, branch,
            entry_time, close_time, fix_change_id, status, reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""

    if status == common.Status.MERGED:
        # Create a row for the merged CL (we don't need to track this), but can be stored
        # to indicate that the changes of this patch are already merged
        # entry_time and close_time are the same since we weren't tracking when it was merged
        print('Bug fix patch [fixes_table_name, kernel_sha, fixedby_upstream_sha] \
                (%s, %s, %s) already merged.' % (
                    fixes_table, kernel_sha, fixedby_upstream_sha))

        reason = 'Patch was not missing (already applied)'
        close_time = entry_time

    elif status == common.Status.OPEN:
        print('TODO(hirthanan) create gerrit ticket for entry \
                kernel_sha:fixedby_upstream_sha', kernel_sha, fixedby_upstream_sha)

        fix_change_id = 0
    elif status == common.Status.CONFLICT:
        # Register conflict entry_time, do not create gerrit CL
        # Requires engineer to manually explore why CL doesn't apply cleanly
        pass

    try:
        c.execute(q, [fixes_table, kernel_sha, fixedby_upstream_sha,
                        branch, entry_time, entry_time, close_time,
                        fix_change_id, cl_status, reason])
        db.commit()
    except MySQLdb.Error as e: # pylint: disable=no-member
        print('Error inserting fix CL into fixes_table',
                [fixes_table, kernel_sha, fixedby_upstream_sha,
                    branch, entry_time, entry_time, close_time, cl_status, reason], e)


def update_fixes_gerrit(db, fixes_table, kernel_sha, upstream_sha, fixedby_upstream_sha):
    """Updates fixes_table rows by attempting to apply a fix change when needed.

    Currently the only way to assign ABANDONED status is to manually do it in DB.
    todo(hirthanan): write process to pull status of CL and update tables
    """
    c = db.cursor()
    q = """SELECT status FROM %s
            WHERE kernel_sha = %s
            AND fixedby_upstream_sha = %s"""
    c.execute(q, [fixes_table, kernel_sha, fixedby_upstream_sha])

    cl_status_row = c.fetchone()
    if not cl_status_row:
        raise ValueError('Database table [%s] should have kernel_sha \
                fixedby_upstream_sha pair row, (%s, %s)' % (
                    fixes_table, kernel_sha, fixedby_upstream_sha))

    prev_cl_status = cl_status_row[0]
    if prev_cl_status == common.Status.OPEN.name:
        # Check to see if upstream sha is merged into linux_chrome already
        q = """SELECT 1 FROM linux_chrome WHERE upstream_sha = %s"""
        c.execute(q, [upstream_sha])
        if c.fetchone():
            cl_status = common.Status.MERGED.name
            close_time = get_current_time()
            reason = 'Closed OPEN CL after merging bugfix patch into linux_chrome'
            q = """UPDATE %s
                    SET status = %s, close_time = %s, reason = %s
                    WHERE kernel_sha = %s
                    AND fixedby_upstream_sha = %s"""
            c.execute(q, [fixes_table, cl_status, close_time, reason,
                            kernel_sha, fixedby_upstream_sha])
        else:
            print('CL [fixes_table, kernel_sha, upstream_sha, fix_usha] \
                    (%s %s %s %s) has not been reviewed yet.' %
                    (fixes_table, kernel_sha, upstream_sha, fixedby_upstream_sha))
    elif prev_cl_status == common.Status.CONFLICT.name:
        # Check to see if fix patch can be applied again, if not do nothing
        status = get_status_from_cherrypicking_sha(fixedby_upstream_sha)
        if status == common.Status.MERGED:
            # Patch is already in linux_chrome
            cl_status = common.Status.MERGED.name
            close_time = get_current_time()
            reason = 'Patch had already been applied to linux_chome'

            q = """UPDATE %s
                    SET status = %s, close_time = %s, reason = %s
                    WHERE kernel_sha = %s
                    AND fixedby_upstream_sha = %s"""
            c.execute(q, [fixes_table, cl_status, close_time, reason,
                            kernel_sha, fixedby_upstream_sha])
        elif status == common.Status.OPEN:
            cl_status = common.Status.OPEN.name
            entry_time = get_current_time()

            # TODO(hirthanan): add api call to gerrit to create ticket
            fix_change_id = 0
            reason = 'Patch is missing and applied cleanly'

            q = """UPDATE %s
                    SET status = %s, entry_time = %s, fix_change_id = %s, reason = %s
                    WHERE kernel_sha = %s
                    AND fixedby_upstream_sha = %s"""
            c.execute(q, [fixes_table, cl_status, entry_time, fix_change_id,
                        reason, kernel_sha, fixedby_upstream_sha])
    elif prev_cl_status == common.Status.MERGED.name or \
            prev_cl_status == common.Status.ABANDONED.name:
        # Nothing needs to be updated
        # todo(hirthanan) handling ABANDONED status extra work if time permits
        return
    else:
        raise ValueError('ERROR, Unknown status type %s' % prev_cl_status)

    db.commit()


def update_fixes(db, fixes_table, branch, kernel_sha, upstream_sha):
    """Keeps track of missing bugfix patches in chrome and stable.

    TODO(hirthanan): Refactor using SQL queries to update conflict, open gerrit statuses.
    """
    c = db.cursor()

    q = """SELECT fixedby_upstream_sha
            FROM linux_upstream_fixes
            WHERE upstream_sha = %s"""
    c.execute(q, [upstream_sha])

    for fix_row in c.fetchall():
        fixedby_upstream_sha = fix_row[0]

        q = """SELECT 1 FROM %s
                WHERE kernel_sha = %s
                AND fixedby_upstream_sha = %s"""
        c.execute(q, [fixes_table, kernel_sha, fixedby_upstream_sha])
        is_sha_fixsha_tracked = c.fetchone()

        # Check if we are already tracking the bugfix
        if is_sha_fixsha_tracked:
            # Update columns if needed
            update_fixes_gerrit(db, fixes_table, kernel_sha, upstream_sha, fixedby_upstream_sha)
        else:
            # Insert new row into table
            insert_fixes_gerrit(db, fixes_table, branch, kernel_sha, fixedby_upstream_sha)


def missing_branch(db, branch, kernel_metadata):
    """Look for missing Fixup commits in provided chromeos or stable release."""
    c = db.cursor()
    bname = kernel_metadata.get_kernel_branch(branch)

    print('Checking branch %s' % bname)
    subprocess.check_output(['git', 'checkout', bname], stderr=subprocess.DEVNULL)

    # TODO(hirthanan) modify to not load entire table
    q = """SELECT sha, upstream_sha
            FROM %s
            WHERE branch = %s"""
    c.execute(q, [kernel_metadata.kernel_table, branch])

    for (sha, upstream_sha) in c.fetchall():
        update_fixes(db, kernel_metadata.kernel_fixes_table, branch, sha, upstream_sha)

    db.commit()


def missing_helper(db, kernel_metadata):
    """Helper to find missing patches in the stable and chromeos releases."""
    if len(sys.argv) > 1:
        branches = sys.argv[1:]
    else:
        branches = common.SUPPORTED_KERNELS

    os.chdir(kernel_metadata.local_kernel_path)

    for b in branches:
        missing_branch(db, b, kernel_metadata)


def missing(db):
    """Finds missing patches in stable and chromeos releases."""
    cur_wd = os.getcwd()

    print('--Missing patches from baseline -> stable.--')
    kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_stable)
    missing_helper(db, kernel_metadata)

    os.chdir(cur_wd)

    print('--Missing patches from baseline -> chromeos.--')
    kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_chrome)
    missing_helper(db, kernel_metadata)

if __name__ == '__main__':
    cloudsql_db = MySQLdb.Connect(user='linux_patches_robot', host='127.0.0.1', db='linuxdb')
    missing(cloudsql_db)
    cloudsql_db.close()
