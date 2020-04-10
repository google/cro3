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
from datetime import datetime

import os
import subprocess
import sys
import time
import MySQLdb

import cloudsql_interface
import common
import gerrit_interface
import missing
import synchronize


def check_service_key_secret_exists():
    """Raises an error if the service account secret key file doesn't exist

    This can be generated on GCP under service accounts (Generate service token)
    This file should automatically be generated when running the gce-startup.sh script.
    """
    cwd = os.getcwd()
    secret_file_path = os.path.join(cwd, 'secrets/linux_patches_robot_key.json')

    if not os.path.exists(secret_file_path):
        raise FileNotFoundError('Service token secret file %s not found' % secret_file_path)


def check_service_running(keyword):
    """Raises an error if there is no running process commands that match `keyword`."""
    process_grep = ['pgrep', '-f', keyword]
    try:
        subprocess.run(process_grep, check=True, stdout=subprocess.DEVNULL,
                        encoding='utf-8', errors='ignore')
    except subprocess.CalledProcessError:
        raise ProcessLookupError('Service %s is not running.' % keyword)


def check_cloud_sql_proxy_running():
    """Raises an error if cloud_sql_proxy service is not running."""
    check_service_running('cloud_sql_proxy')


def check_git_cookie_authdaemon_running():
    """Raises an error if git-cookie-authdaemon service is not running."""
    check_service_running('git-cookie-authdaemon')


def preliminary_check_decorator(is_gce):
    """Decorator for performing environment related checks."""
    def wrap_preliminary_check(f):
        """Inner function that wraps method with preliminary check."""
        def wrapped_preliminary_check(*args):
            """Sanity checks on state of environment before executing decorated function."""
            if is_gce:
                # Ensures we have service account credentials to connect to cloudsql (GCP)
                check_service_key_secret_exists()

            # Ensure cloudsql proxy is running to allow connection
            check_cloud_sql_proxy_running()

            if is_gce:
                # Ensure we have token to allow service account to perform Gerrit API operations
                check_git_cookie_authdaemon_running()

            f(*args)
        return wrapped_preliminary_check
    return wrap_preliminary_check


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


@preliminary_check_decorator(True)
def synchronize_and_create_patches():
    """Synchronize repositories/databases + create new fixes."""
    current_time = datetime.now()
    sync_repositories_and_databases()

    # This depends on cron jobs starting at 0 UTC
    #  Ensures that we only create new patches once a day
    if current_time.hour == 0:
        create_new_patches()


def set_gcloud_project_config():
    """Sets project settings to chromeos-missing-patches project."""
    set_project_cmd = ['gcloud', 'config', 'set', 'project', 'google.com:chromeos-missing-patches']
    subprocess.run(set_project_cmd, stderr=subprocess.DEVNULL, check=True)


def cloud_sql_proxy_decorator(func):
    """Decorator for starting and stopping cloud_sql_proxy."""
    def cloud_sql_proxy_wrapper(*args, **kwargs):
        """Create cloud_sql_proxy process, run func, send signal.SIGKILL cloud_sql_proxy"""
        try:
            set_gcloud_project_config()
            sql_instance_cmd = ['gcloud', 'sql', 'instances', 'describe',
                                'linux-patches-sql', '--format=value[](connectionName)']
            sql_instance = subprocess.check_output(sql_instance_cmd, encoding='utf-8').rstrip()

            cloudsql_cmd = ['cloud_sql_proxy', '-instances=%s=tcp:3306' % sql_instance]
            cloud_sql_proxy_pid = subprocess.Popen(cloudsql_cmd, stdout=subprocess.DEVNULL,
                                                    stderr=subprocess.DEVNULL)

            # Wait for cloud_sql_proxy to spin up
            # todo(hirthanan): read cloud_sql pipe to see when it starts up
            time.sleep(3)

            func(*args, **kwargs)

            cloud_sql_proxy_pid.kill()
        except subprocess.CalledProcessError:
            print('Failed to retrieve sql_instance from gcloud')
            print('User must be authenticated with Cloud SDK (run `gcloud auth login`)')
            print('User must also be added to GCP project chromeos-missing-patches.')
            raise
    return cloud_sql_proxy_wrapper


@cloud_sql_proxy_decorator
@preliminary_check_decorator(False)
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


@cloud_sql_proxy_decorator
@preliminary_check_decorator(False)
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
