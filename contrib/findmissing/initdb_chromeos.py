#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module rebuilding database with metadata about chromeos patches."""

from __future__ import print_function
import re
import subprocess
import MySQLdb
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
    subprocess.run(['git', 'checkout', common.chromeos_branch(branch)], check=True)
    subprocess.run(['git', 'pull'], check=True)

    subprocess_cmd = ['git', 'log', '--no-merges', '--abbrev=12',
                      '--oneline', '--reverse', '%s..' % start]
    commits = subprocess.check_output(subprocess_cmd, encoding='utf-8', errors='ignore')

    c = db.cursor()
    last = None
    print('Parsing git logs from %s .. HEAD on branch %s' %
            (start, common.chromeos_branch(branch)))

    for commit in commits.splitlines():
        if commit:
            elem = commit.split(' ', 1)
            sha = elem[0]

            description = elem[1].rstrip('\n')

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

            last = sha

            usha = None
            if not CHROMIUM.match(description):
                usha = common.search_upstream_sha(sha)

            try:
                q = """INSERT INTO linux_chrome
                        (sha, branch, upstream_sha, patch_id, description)
                        VALUES (%s, %s, %s, %s, %s)"""
                c.execute(q, [sha, branch, usha, patchid, description])
                print('Insert into linux_chrome', [sha, branch, usha, patchid, description])
            except MySQLdb.Error as e: # pylint: disable=no-member
                print('Error in insertion into linux_chrome with values: ',
                        [sha, branch, usha, patchid, description], e)
            except UnicodeDecodeError as e:
                print('Failed to INSERT stable sha %s with desciption %s'
                        % (sha, description), e)

    # Update previous fetch database
    if last:
        common.update_previous_fetch(db, common.Kernel.linux_chrome, branch, last)

    db.commit()



if __name__ == '__main__':
    cloudsql_db = MySQLdb.Connect(user='linux_patches_robot', host='127.0.0.1', db='linuxdb')
    kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_chrome)
    common.update_kernel_db(cloudsql_db, kernel_metadata)
    cloudsql_db.close()
