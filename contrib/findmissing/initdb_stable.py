#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module parses and stores data from stable linux patch."""

from __future__ import print_function
import sqlite3
import os
import subprocess
from common import STABLE_PATH, SUPPORTED_KERNELS, \
        WORKDIR, CHERRYPICK, STABLE, STABLE2, make_downstream_table, \
        stabledb, stable_branch, createdb


def search_usha(sha):
    """Search for upstream SHA.

    If found, return upstream SHA associated with this commit sha.
    """

    usha = ''
    desc = subprocess.check_output(['git', 'show',
        '-s', sha]).decode('utf-8', errors='ignore')
    for d in desc.splitlines():
        m = CHERRYPICK.search(d)
        if not m:
            m = STABLE.search(d)
            if not m:
                m = STABLE2.search(d)
        if m:
            # The patch may have been picked multiple times; only record
            # the first entry.
            usha = m.group(2)[:12]
            return usha
    return usha


def update_commits(start, db):
    """Get complete list of commits from stable branch.

    Assume that stable branch exists and has been checked out.
    """

    conn = sqlite3.connect(db)
    conn.text_factory = str
    c = conn.cursor()

    cmd = ['git', 'log', '--no-merges', '--abbrev=12', '--oneline',
                 '--reverse', '%s..' % start]
    commits = subprocess.check_output(cmd).decode('utf-8', errors='ignore')

    last = None
    for commit in commits.splitlines():
        if commit:
            elem = commit.split(' ', 1)
            sha = elem[0]
            description = elem[1].rstrip('\n')

            ps = subprocess.Popen(['git', 'show', sha], stdout=subprocess.PIPE)
            spid = subprocess.check_output(['git', 'patch-id', '--stable'],
                            stdin=ps.stdout).decode('utf-8', errors='ignore')
            patchid = spid.split(' ', 1)[0]

            # Do nothing if the sha is already in the database
            c.execute("select sha from commits where sha='%s'" % sha)
            found = c.fetchone()
            if found:
                continue

            last = sha
            usha = search_usha(sha)

            c.execute('INSERT INTO commits(sha, usha,' \
                                'patchid, description, changeid) VALUES (?, ?, ?, ?, ?)',
                                (sha, usha, patchid, description, None))
    if last:
        c.execute("UPDATE tip set sha='%s' where ref=1" % last)

    conn.commit()
    conn.close()


def update_stabledb():
    """Updates the stabledb index for all stable branches."""
    os.chdir(STABLE_PATH)

    for branch in SUPPORTED_KERNELS:
        start = 'v%s' % branch
        db = stabledb(branch)
        bname = stable_branch(branch)

        print('Handling %s' % bname)

        try:
            conn = sqlite3.connect(db)
            conn.text_factory = str

            c = conn.cursor()
            c.execute('select sha from tip')
            sha = c.fetchone()
            conn.close()
            if sha and sha[0] != '':
                start = sha[0]
        except sqlite3.Error:
            createdb(db, make_downstream_table)

        subprocess.check_output(['git', 'checkout', bname])
        subprocess.check_output(['git', 'pull'])

        update_commits(start, db)

    os.chdir(WORKDIR)


if __name__ == '__main__':
    update_stabledb()
