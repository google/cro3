#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Main interface for users/automated systems to run commands.

Systems will include: Cloud Scheduler, CloudSQL, and Compute Engine
"""

from __future__ import print_function

import sys
import MySQLdb

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


@util.cloud_sql_proxy_decorator
@util.preliminary_check_decorator(False)
def abandon_fix_cl(fixes_table, kernel_sha, fixedby_upstream_sha, reason):
    """Abandons an fix CL + updates database fix table."""
    cloudsql_db = MySQLdb.Connect(user='linux_patches_robot', host='127.0.0.1', db='linuxdb')
    try:
        row = cloudsql_interface.get_fix_status_and_changeid(cloudsql_db, fixes_table,
                                                    kernel_sha, fixedby_upstream_sha)
        if not row:
            print('Patch %s Fixed By %s doesnt exist in list of fixes in %s'
                                % (kernel_sha, fixedby_upstream_sha, fixes_table))
            sys.exit(1)
        if row['status'] == common.Status.OPEN.name:
            fix_change_id = row['fix_change_id']
            branch = row['branch']
            gerrit_interface.abandon_change(fix_change_id, branch, reason)
            print('Abandoned Change %s on Gerrit with reason %s' % (fix_change_id, reason))
        cloudsql_interface.update_change_abandoned(cloudsql_db, fixes_table,
                                                    kernel_sha, fixedby_upstream_sha, reason)
        print('Updated status to abandoned for Patch %s Fixed by %s'
                % (kernel_sha, fixedby_upstream_sha))
        sys.exit(0)
    except KeyError:
        print("""Could not retrieve fix row with primary key kernel_sha %s
                    and fixedby_upstream_sha %s""" % (kernel_sha, fixedby_upstream_sha))
        sys.exit(1)
    finally:
        cloudsql_db.close()


@util.cloud_sql_proxy_decorator
@util.preliminary_check_decorator(False)
def restore_fix_cl(fixes_table, kernel_sha, fixedby_upstream_sha, reason):
    """Restores an abandoned change + updates database fix table."""
    cloudsql_db = MySQLdb.Connect(user='linux_patches_robot', host='127.0.0.1', db='linuxdb')
    try:
        row = cloudsql_interface.get_fix_status_and_changeid(cloudsql_db, fixes_table,
                                                    kernel_sha, fixedby_upstream_sha)
        if not row:
            print('Patch %s Fixed By %s doesnt exist in list of fixes in %s'
                                % (kernel_sha, fixedby_upstream_sha, fixes_table))
            sys.exit(1)
        if row['status'] == common.Status.ABANDONED.name:
            fix_change_id = row.get('fix_change_id')
            if fix_change_id:
                branch = row['branch']
                gerrit_interface.restore_change(fix_change_id, branch, reason)
                print('Restored Change %s on Gerrit with reason %s' % (fix_change_id, reason))
            cloudsql_interface.update_change_restored(cloudsql_db, fixes_table,
                                                    kernel_sha, fixedby_upstream_sha, reason)
            print('Updated status to restored for Patch %s Fixed by %s'
                    % (kernel_sha, fixedby_upstream_sha))
            sys.exit(0)
    except KeyError:
        print("""Could not retrieve fix row with primary key kernel_sha %s
                    and fixedby_upstream_sha %s""" % (kernel_sha, fixedby_upstream_sha))
        sys.exit(1)
    finally:
        cloudsql_db.close()
