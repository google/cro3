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


def get_fix_status_and_changeid(db, fixes_table, kernel_sha, fixedby_upstream_sha):
    """Get initial_status, status, and fix_change_id row from fixes table."""
    c = db.cursor(MySQLdb.cursors.DictCursor)

    q = """SELECT initial_status, status, fix_change_id
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
