#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Find missing stable and backported mainline fix patches in chromeos."""

from __future__ import print_function

import MySQLdb

import common

DEFAULT_MERGED_REASON = 'Fix merged into linux chrome'

def get_fixes_table_primary_key(db, fixes_table, fix_change_id):
    """Retrieves the primary keys from a fixes table using changeid."""
    c = db.cursor(MySQLdb.cursors.DictCursor)

    q = """SELECT kernel_sha, fixedby_upstream_sha
            FROM {fixes_table}
            WHERE fix_change_id = %s""".format(fixes_table=fixes_table)

    c.execute(q, [fix_change_id])
    row = c.fetchone()
    return (row['kernel_sha'], row['fixedby_upstream_sha'])


def get_fix_status_and_changeid(db, fixes_table, kernel_sha, fixedby_upstream_sha):
    """Get branch, fix_change_id, initial_status and status for a unique row in fixes table."""
    c = db.cursor(MySQLdb.cursors.DictCursor)

    q = """SELECT branch, fix_change_id, initial_status, status
            FROM {fixes_table}
            WHERE kernel_sha = %s
            AND fixedby_upstream_sha = %s""".format(fixes_table=fixes_table)

    c.execute(q, [kernel_sha, fixedby_upstream_sha])
    row = c.fetchone()
    return row


def update_change_abandoned(db, fixes_table, kernel_sha, fixedby_upstream_sha):
    """Updates fixes_table unique fix row to indicate fix cl has been abandoned.

    Function will only abandon rows in the table which have status OPEN or CONFLICT.
    """
    c = db.cursor()
    q = """UPDATE {fixes_table}
            SET status = 'ABANDONED', close_time = %s
            WHERE kernel_sha = %s
            AND fixedby_upstream_sha = %s
            AND (status = 'OPEN' OR status = 'CONFLICT')""".format(fixes_table=fixes_table)
    close_time = common.get_current_time()
    c.execute(q, [close_time, kernel_sha, fixedby_upstream_sha])
    db.commit()


def update_change_restored(db, fixes_table, kernel_sha, fixedby_upstream_sha):
    """Updates fixes_table unique fix row to indicate fix cl has been reopened."""
    row = get_fix_status_and_changeid(db, fixes_table, kernel_sha, fixedby_upstream_sha)
    initial_status = row['initial_status']

    c = db.cursor()
    q = """UPDATE {fixes_table}
            SET status = %s, close_time = %s
            WHERE kernel_sha = %s
            AND fixedby_upstream_sha = %s
            AND status = 'ABANDONED'""".format(fixes_table=fixes_table)
    close_time = None
    c.execute(q, [initial_status, close_time, kernel_sha, fixedby_upstream_sha])
    db.commit()


def update_change_merged(db, fixes_table, kernel_sha, fixedby_upstream_sha,
                            reason=DEFAULT_MERGED_REASON):
    """Updates fixes_table unique fix row to indicate fix cl has been merged."""
    c = db.cursor()
    q = """UPDATE {fixes_table}
            SET status = 'MERGED', close_time = %s, reason = %s
            WHERE kernel_sha = %s
            AND fixedby_upstream_sha = %s""".format(fixes_table=fixes_table)
    close_time = common.get_current_time()
    c.execute(q, [close_time, reason, kernel_sha, fixedby_upstream_sha])
    db.commit()


def update_change_status(db, fixes_table, fix_change_id, status):
    """Updates fixes_table with the latest status from Gerrit API.

    This is done to synchronize CL's that are
    abandoned/restored on Gerrit with our database state
    """
    kernel_sha, fixedby_upstream_sha = get_fixes_table_primary_key(db, fixes_table, fix_change_id)
    if status == common.Status.OPEN:
        update_change_restored(db, fixes_table, kernel_sha, fixedby_upstream_sha)
    elif status == common.Status.ABANDONED:
        update_change_abandoned(db, fixes_table, kernel_sha, fixedby_upstream_sha)
    elif status == common.Status.MERGED:
        update_change_merged(db, fixes_table, kernel_sha, fixedby_upstream_sha)
    else:
        raise ValueError('Change should be either OPEN, ABANDONED, or MERGED')


def update_conflict_to_open(db, fixes_table, kernel_sha, fixedby_upstream_sha, fix_change_id):
    """Updates fixes_table to represent an open change that previously resulted in conflict."""
    c = db.cursor()
    reason = 'Patch applies cleanly after originally conflicting.'
    q = """UPDATE {fixes_table}
            SET status = 'OPEN', fix_change_id = %s, reason = %s
            WHERE kernel_sha = %s
            AND fixedby_upstream_sha = %s""".format(fixes_table=fixes_table)
    c.execute(q, [fix_change_id, reason, kernel_sha, fixedby_upstream_sha])
    db.commit()
