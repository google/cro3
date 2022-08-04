#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module parses and stores data from stable linux patch.

   isort:skip_file
"""

import contextlib
import logging
import subprocess

import MySQLdb # pylint: disable=import-error

import common


def update_stable_table(branch, start, db):
    """Updates the linux stable commits table.

    Also keep a reference of last parsed SHA so we don't have to index the
        entire commit log on each run.
    """
    cursor = db.cursor()

    # Pull latest changes in repository
    subprocess.check_output(['git', 'checkout', '-q', common.stable_branch(branch)])
    subprocess.check_output(['git', 'pull', '-q'])

    cmd = ['git', 'log', '--no-merges', '--abbrev=12', '--oneline',
                 '--reverse', '%s..' % start]
    commits = subprocess.check_output(cmd, encoding='utf-8', errors='ignore')

    last = None
    for commit in commits.splitlines():
        if commit:
            elem = commit.split(' ', 1)
            sha = elem[0]

            description = elem[1].rstrip('\n')

            ps = subprocess.Popen(['git', 'show', sha], stdout=subprocess.PIPE)
            spid = subprocess.check_output(['git', 'patch-id', '--stable'],
                            stdin=ps.stdout, encoding='utf-8', errors='ignore')
            patch_id = spid.split(' ', 1)[0]

            # Do nothing if the sha is already in the database
            q = """SELECT sha FROM linux_stable
                    WHERE sha = %s"""
            cursor.execute(q, [sha])
            found = cursor.fetchone()
            if found:
                continue

            last = sha
            usha = common.search_upstream_sha(sha)

            # The upstream SHA will not always exist, for example for commits
            # changing the Linux version number. Attempts to insert such commits
            # into linux_stable will fail, so ignore them.
            if usha is None:
                continue

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
    with contextlib.closing(common.connect_db()) as cloudsql_db:
        kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_stable)
        common.update_kernel_db(cloudsql_db, kernel_metadata)
