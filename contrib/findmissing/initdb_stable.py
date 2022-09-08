#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module parses and stores data from stable linux patch.

   isort:skip_file
"""

import logging
import subprocess

import MySQLdb # pylint: disable=import-error

import common
import util


def update_stable_table(branch, start, db):
    """Updates the linux stable commits table.

    Also keep a reference of last parsed SHA so we don't have to index the
        entire commit log on each run.
    """
    logging.info('Linux stable on branch %s', branch)
    cursor = db.cursor()

    logging.info('Pulling all the latest linux stable commits')
    subprocess.check_output(['git', 'checkout', common.stable_branch(branch)])
    subprocess.check_output(['git', 'pull'])

    logging.info('Loading all linux stable commit logs from %s', start)
    cmd = ['git', 'log', '--no-merges', '--abbrev=12', '--oneline',
                '--reverse', '%s..' % start]
    commits = subprocess.check_output(cmd, encoding='utf-8', errors='ignore')

    last = None
    logging.info('Analyzing commits to build linux_stable table.')

    for commit in commits.splitlines():
        if not commit:
            continue

        sha, description = commit.rstrip('\n').split(' ', 1)
        last = sha

        # Do nothing if the sha is already in the database
        q = """SELECT 1 FROM linux_stable WHERE sha = %s"""
        cursor.execute(q, [sha])
        if cursor.fetchone():
            continue

        usha = common.search_upstream_sha(sha)
        # The upstream SHA will not always exist, for example for commits
        # changing the Linux version number. Attempts to insert such commits
        # into linux_stable will fail, so ignore them.
        if usha is None:
            continue

        # Calculate patch ID
        patch_id = util.calc_patch_id(sha, stable=True)

        try:
            q = """INSERT INTO linux_stable
                    (sha, branch, upstream_sha, patch_id, description)
                    VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(q, [sha, branch, usha, patch_id, description])
            logging.info('Insert into linux_stable %s %s %s %s %s',
                         sha, branch, usha, patch_id, description)
        except MySQLdb.Error as e: # pylint: disable=no-member
            logging.error(
                'Error inserting into linux_stable with values %s %s %s %s %s: error %d (%s)',
                sha, branch, usha, patch_id, description, e.args[0], e.args[1])
        except UnicodeDecodeError as e:
            logging.error(
                'Failed to INSERT stable sha %s with description %s: error %s',
                sha, description, e)

    # Update previous fetch database
    if last:
        common.update_previous_fetch(db, common.Kernel.linux_stable, branch, last)

    db.commit()


if __name__ == '__main__':
    with common.connect_db() as cloudsql_db:
        kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_stable)
        common.update_kernel_db(cloudsql_db, kernel_metadata)
