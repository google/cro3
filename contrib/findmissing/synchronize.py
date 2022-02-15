#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Setup module containing script to Synchronize kernel repositories + database."""


import logging
import os
import subprocess
import MySQLdb # pylint: disable=import-error
import common

import cloudsql_interface
import gerrit_interface
import git_interface

UPSTREAM_KERNEL_METADATA = common.get_kernel_metadata(common.Kernel.linux_upstream)
STABLE_KERNEL_METADATA = common.get_kernel_metadata(common.Kernel.linux_stable)
CHROME_KERNEL_METADATA = common.get_kernel_metadata(common.Kernel.linux_chrome)

def synchronize_upstream(upstream_kernel_metadata):
    """Synchronizes locally cloned repo with linux upstream remote."""
    destdir = common.get_kernel_absolute_path(upstream_kernel_metadata.path)
    repo = upstream_kernel_metadata.repo

    if not os.path.exists(destdir):
        logging.info('Cloning %s into %s', repo, destdir)
        clone = ['git', 'clone', '-q', repo, destdir]
        subprocess.run(clone, check=True)
    else:
        logging.info('Pulling latest changes in %s into %s', repo, destdir)
        handler = git_interface.commitHandler(common.Kernel.linux_upstream, 'master')
        handler.pull()

    os.chdir(common.WORKDIR)


def synchronize_custom(kernel):
    """Synchronizes locally cloned repo with linux stable/chromeos remote."""

    metadata = common.get_kernel_metadata(kernel)
    destdir = common.get_kernel_absolute_path(metadata.path)
    upstream_destdir = common.get_kernel_absolute_path(common.UPSTREAM_PATH)
    repo = metadata.repo

    if not os.path.exists(destdir):
        logging.info('Cloning %s into %s', repo, destdir)
        clone = ['git', 'clone', '-q', repo, destdir]
        subprocess.run(clone, check=True)

        os.chdir(destdir)
        for branch in metadata.branches:
            branch_name = metadata.get_kernel_branch(branch)

            logging.info('Creating local branch %s in destdir %s', branch_name, destdir)
            checkout_branch = ['git', 'checkout', '-q', branch_name]
            subprocess.run(checkout_branch, check=True)

        logging.info('Add remote upstream %s to destdir %s', upstream_destdir, destdir)
        add_upstream_remote = ['git', 'remote', 'add', 'upstream', upstream_destdir]
        fetch_upstream = ['git', 'fetch', '-q', 'upstream']
        subprocess.run(add_upstream_remote, check=True)
        subprocess.run(fetch_upstream, check=True)
        os.chdir(common.WORKDIR)
    else:
        logging.info('Updating %s into %s', repo, destdir)

        handler = git_interface.commitHandler(kernel)
        handler.fetch()
        handler.fetch('upstream')
        for branch in metadata.branches:
            branch_name = metadata.get_kernel_branch(branch)
            logging.info('Updating local branch %s in destdir %s', branch_name, destdir)
            handler.pull(branch)


def synchronize_repositories(local=False):
    """Deep clones linux_upstream, linux_stable, and linux_chromeos repositories"""
    synchronize_upstream(UPSTREAM_KERNEL_METADATA)
    synchronize_custom(common.Kernel.linux_stable)
    synchronize_custom(common.Kernel.linux_chrome)
    if local:
        synchronize_custom(common.Kernel.linux_stable_rc)


def synchronize_databases():
    """Synchronizes the databases for upstream, stable, and chromeos."""
    db = MySQLdb.Connect(user='linux_patches_robot', host='127.0.0.1', db='linuxdb',
                         charset='utf8mb4')
    common.update_kernel_db(db, UPSTREAM_KERNEL_METADATA)
    common.update_kernel_db(db, STABLE_KERNEL_METADATA)
    common.update_kernel_db(db, CHROME_KERNEL_METADATA)
    db.close()


def gerrit_status_to_db_status(gerrit_status):
    """Translates gerrit status to common.Status structure."""
    gerrit_to_db_status = {'NEW': common.Status.OPEN,
                            'ABANDONED': common.Status.ABANDONED,
                            'MERGED': common.Status.MERGED}
    return gerrit_to_db_status[gerrit_status]

def synchronize_fixes_tables_with_gerrit():
    """Synchronizes the state of all OPEN/ABANDONED CL's with Gerrit."""
    db = MySQLdb.Connect(user='linux_patches_robot', host='127.0.0.1', db='linuxdb',
                         charset='utf8mb4')
    c = db.cursor(MySQLdb.cursors.DictCursor)

    # Find all OPEN/ABANDONED CL's in chrome_fixes
    fixes_tables = ['stable_fixes', 'chrome_fixes']

    for fixes_table in fixes_tables:
        q = """SELECT branch, fix_change_id
                FROM {fixes_table}
                WHERE (status = 'OPEN' OR status = 'ABANDONED')
                AND fix_change_id IS NOT NULL""".format(fixes_table=fixes_table)
        c.execute(q)
        rows = c.fetchall()

        for row in rows:
            try:
                branch = row['branch']
                fix_change_id = row['fix_change_id']
                gerrit_status = gerrit_interface.get_status(fix_change_id, branch)
                status = gerrit_status_to_db_status(gerrit_status)
                cloudsql_interface.update_change_status(db, fixes_table, fix_change_id, status)
            except KeyError as e:
                logging.warning('Skipping syncing change-id %s with gerrit (%s)',
                                fix_change_id, e)

    db.close()


if __name__ == '__main__':
    synchronize_repositories()
    synchronize_databases()
