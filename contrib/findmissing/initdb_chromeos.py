#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module rebuilding database with metadata about chromeos patches.

   isort:skip_file
"""

import contextlib
import logging
import re
import subprocess

import MySQLdb.constants.ER # pylint: disable=import-error
import MySQLdb # pylint: disable=import-error

import common


UPSTREAM = re.compile(r'(ANDROID: *|UPSTREAM: *|FROMGIT: *|BACKPORT: *)+(.*)')
CHROMIUM = re.compile(r'(CHROMIUM: *|FROMLIST: *)+(.*)')
CHANGEID = re.compile(r'^( )*Change-Id: [a-zA-Z0-9]*$')


def update_chrome_table(branch, start, db):
    """Updates the linux chrome commits table.

    Also keep a reference of last parsed SHA so we don't have to index the
        entire commit log on each run.
    Skip commit if it is contained in the linux stable db, add to linux_chrome
    """
    subprocess.run(['git', 'checkout', '-q', common.chromeos_branch(branch)], check=True)
    subprocess.run(['git', 'pull', '-q'], check=True)

    cmd = ['git', 'log', '--abbrev=12', '--oneline', '--reverse', '%s..' % start]
    commits = subprocess.check_output(cmd, encoding='utf-8', errors='ignore')

    c = db.cursor()
    last = None
    logging.info('Parsing git logs from %s .. HEAD on branch %s',
                 start, common.chromeos_branch(branch))

    for commit in commits.splitlines():
        if commit:
            elem = commit.split(' ', 1)
            sha = elem[0]

            description = elem[1].rstrip('\n')

            # Always mark as handled since we don't want to look at this commit again
            last = sha

            # Nothing else to do if the commit is a merge
            l = subprocess.check_output(['git', 'rev-list', '--parents', '-n', '1', sha],
                                        encoding='utf-8', errors='ignore')
            if len(l.split(' ')) > 2:
                continue

            ps = subprocess.Popen(['git', 'show', sha], stdout=subprocess.PIPE)
            spid = subprocess.check_output(['git', 'patch-id', '--stable'],
                    stdin=ps.stdout, encoding='utf-8', errors='ignore')
            patchid = spid.split(' ', 1)[0]

            # Do nothing if sha is in linux_stable since we
            #  don't want to duplicate tracking linux_stable sha's
            q = """SELECT 1 FROM linux_stable
                    WHERE sha = %s"""
            c.execute(q, [sha])
            stable_found = c.fetchone()

            if stable_found:
                continue

            usha = None
            if not CHROMIUM.match(description):
                usha = common.search_upstream_sha(sha)

            try:
                q = """INSERT INTO linux_chrome
                        (sha, branch, upstream_sha, patch_id, description)
                        VALUES (%s, %s, %s, %s, %s)"""
                c.execute(q, [sha, branch, usha, patchid, description])
                logging.info('Insert into linux_chrome %s %s %s %s %s',
                             sha, branch, usha, patchid, description)
            except MySQLdb.Error as e: # pylint: disable=no-member
                # We'll see duplicates if the last commit handled previously was
                # the tip of a merge. In that case, all commits from the tail of
                # that merge up to the time when it was integrated will be handled
                # again. Let's ignore that situation.
                if e.args[0] != MySQLdb.constants.ER.DUP_ENTRY:
                    logging.error(
                        'Error inserting [%s %s %s %s %s] into linux_chrome: error %d (%s)',
                        sha, branch, usha, patchid, description, e.args[0], e.args[1])
            except UnicodeDecodeError as e:
                logging.error(
                        'Unicode error inserting [%s %s %s %s %s] into linux_chrome: error %s',
                        sha, branch, usha, patchid, description, e)

    # Update previous fetch database
    if last:
        common.update_previous_fetch(db, common.Kernel.linux_chrome, branch, last)

    db.commit()



if __name__ == '__main__':
    with contextlib.closing(common.connect_db()) as cloudsql_db:
        kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_chrome)
        common.update_kernel_db(cloudsql_db, kernel_metadata)
