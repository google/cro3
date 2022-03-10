#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Main interface for users/automated systems to run commands.

Systems will include: Cloud Scheduler, CloudSQL, and Compute Engine
"""


import sys

import cloudsql_interface
import common
import gerrit_interface
import missing
import synchronize
import util


def sync_repositories_and_databases():
    """Synchronizes repositories, databases, missing patches, and status with gerrit."""
    synchronize.synchronize_repositories()
    synchronize.synchronize_databases()
    synchronize.synchronize_fixes_tables_with_gerrit()

    # Updates fixes table entries on regular basis by checking
    #  if any OPEN/CONFL fixes have been merged.
    missing.update_missing_patches()


def create_new_patches():
    """Creates a new patch for each branch in chrome and stable linux."""
    missing.new_missing_patches()


@util.preliminary_check_decorator(True)
def synchronize_and_create_patches(create_patches=False):
    """Synchronize repositories/databases + create new fixes."""
    sync_repositories_and_databases()

    if create_patches:
        create_new_patches()


def print_rows(rows):
    """Print list of SHAs in database"""
    print('Table   Branch  SHA             Fixed by SHA    Status')
    for row in rows:
        print('%-8s%-8s%-16s%-16s%s' %
              (row['table'].replace('_fixes', ''),
               row['branch'], row['kernel_sha'], row['fixedby_upstream_sha'], row['status']))


def get_fixes_rows(cloudsql_db, fixes_table, sha_list, strict):
    """Get all table rows for provided fixes table, or for both tables if none is proviced."""

    if not fixes_table:
        fixes_tables = ['stable_fixes', 'chrome_fixes']
    else:
        fixes_tables = [fixes_table]

    return cloudsql_interface.get_fix_status_and_changeid(cloudsql_db, fixes_tables, sha_list,
                                                          strict)


@util.cloud_sql_proxy_decorator
@util.preliminary_check_decorator(False)
def abandon_fix_cl(fixes_table, sha_list, reason, force):
    """Abandons an fix CL + updates database fix table."""
    cloudsql_db = common.connect_db()

    try:
        rows = get_fixes_rows(cloudsql_db, fixes_table, sha_list, True)
        if not rows:
            print('Patch identified by "%s" not found in fixes table(s)' % sha_list)
            sys.exit(1)
        if len(rows) > 1 and not force:
            print('More than one database entry. Force flag needed to continue.')
            print_rows(rows)
            sys.exit(1)
        for row in rows:
            branch = row['branch']
            fixedby_upstream_sha = row['fixedby_upstream_sha']
            kernel_sha = row['kernel_sha']
            status = row['status']
            if status == common.Status.ABANDONED.name:
                continue
            if status not in (common.Status.OPEN.name, common.Status.CONFLICT.name):
                print('Status for SHA %s fixed by %s is %s, can not abandon' %
                      (kernel_sha, fixedby_upstream_sha, status))
                continue
            if status == common.Status.OPEN.name:
                fix_change_id = row['fix_change_id']
                gerrit_interface.abandon_change(fix_change_id, branch, reason)
                print('Abandoned Change %s on Gerrit with reason %s' % (fix_change_id, reason))
            cloudsql_interface.update_change_abandoned(cloudsql_db, row['table'],
                                                       kernel_sha, fixedby_upstream_sha, reason)
            print('Updated status to abandoned for patch %s in %s, fixed by %s' %
                  (kernel_sha, branch, fixedby_upstream_sha))
        sys.exit(0)
    except KeyError:
        print("""Could not retrieve fix row with primary key kernel_sha %s
                    and fixedby_upstream_sha %s""" % (kernel_sha, fixedby_upstream_sha))
        sys.exit(1)
    finally:
        cloudsql_db.close()


@util.cloud_sql_proxy_decorator
@util.preliminary_check_decorator(False)
def status_fix_cl(fixes_table, sha_list, reason, force): # pylint: disable=unused-argument
    """Lists status for a fix CL."""
    db = common.connect_db()

    rows = []
    # Remove duplicate SHAs
    sha_list = list(set(sha_list))
    rows = get_fixes_rows(db, fixes_table, sha_list, False)
    if not rows:
        print('No patches identified by "%s" found in fixes table(s)' % sha_list)
    else:
        print_rows(rows)

    db.close()


@util.cloud_sql_proxy_decorator
@util.preliminary_check_decorator(False)
def restore_fix_cl(fixes_table, sha_list, reason, force):
    """Restores an abandoned change + updates database fix table."""
    cloudsql_db = common.connect_db()
    try:
        rows = get_fixes_rows(cloudsql_db, fixes_table, sha_list, True)
        if not rows:
            print('Patch identified by "%s" not found in fixes table(s)' % sha_list)
            sys.exit(1)
        if len(rows) > 1 and not force:
            print('More than one database entry. Force flag needed to continue.')
            print_rows(rows)
            sys.exit(1)
        for row in rows:
            if row['status'] != common.Status.ABANDONED.name:
                continue
            fix_change_id = row['fix_change_id']
            branch = row['branch']
            fixedby_upstream_sha = row['fixedby_upstream_sha']
            kernel_sha = row['kernel_sha']
            if fix_change_id:
                gerrit_interface.restore_change(fix_change_id, branch, reason)
                print('Restored Change %s on Gerrit with reason %s' % (fix_change_id, reason))
            cloudsql_interface.update_change_restored(cloudsql_db, row['table'],
                                                      kernel_sha, fixedby_upstream_sha, reason)
            print('Updated status to restored for patch %s in %s, fixed by %s'
                  % (kernel_sha, branch, fixedby_upstream_sha))
        sys.exit(0)
    except KeyError:
        print("""Could not retrieve fix row with primary key kernel_sha %s
                    and fixedby_upstream_sha %s""" % (kernel_sha, fixedby_upstream_sha))
        sys.exit(1)
    finally:
        cloudsql_db.close()
