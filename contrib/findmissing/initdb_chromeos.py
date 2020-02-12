#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module rebuilding database with metadata about chromeos patches."""

from __future__ import print_function
import sqlite3
import os
import re
import subprocess
from common import CHROMEOS_PATH, SUPPORTED_KERNELS, \
        WORKDIR, CHERRYPICK, STABLE, STABLE2, make_downstream_table, \
        stabledb, chromeosdb, chromeos_branch, createdb

UPSTREAM = re.compile(r'(ANDROID: *|UPSTREAM: *|FROMGIT: *|BACKPORT: *)+(.*)')
CHROMIUM = re.compile(r'(CHROMIUM: *|FROMLIST: *)+(.*)')
CHANGEID = re.compile(r'^( )*Change-Id: [a-zA-Z0-9]*$')


def parse_changeID(chromeos_sha):
    """String searches for Change-Id in a chromeos git commit.

    Returns Change-Id or None if commit doesn't have associated Change-Id
    """
    commit = subprocess.check_output(['git', 'show', \
            chromeos_sha]).decode('utf-8', errors='ignore')

    for line in commit.splitlines():
        if CHANGEID.match(line):
            # removes whitespace prefixing Change-Id
            line = line.lstrip()
            commit_changeID = line[(line.index(' ') + 1):]
            return commit_changeID

    return None


def search_usha(sha, description):
    """Search for upstream SHA.

    If found, return upstream sha associated with this commit sha.
    """

    usha = ''
    if not CHROMIUM.match(description):
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



def update_commits(start, cdb, sdb):
    """Get list of commits from selected branch, starting with commit 'start'.

    Branch must be checked out in current directory.
    Skip commit if it is contained in sdb, otherwise add to cdb if it isn't
    already there.
    """

    try:
        conn = sqlite3.connect(cdb)
        conn.text_factory = str
        c = conn.cursor()

        sconn = sqlite3.connect(sdb)
        sconn.text_factory = str
        sc = sconn.cursor()
    except sqlite3.Error as e:
        print('Could not update chromeos commits, raising error: ', e)
        raise

    subprocess_cmd = ['git', 'log', '--no-merges', '--abbrev=12',
                      '--oneline', '--reverse', '%s..' % start]
    commits = subprocess.check_output(subprocess_cmd).decode('utf-8')

    last = None
    for commit in commits.splitlines():
        if commit:
            elem = commit.split(' ', 1)
            sha = elem[0]
            description = elem[1].rstrip('\n')
            ps = subprocess.Popen(['git', 'show', sha],
                    stdout=subprocess.PIPE, encoding='utf-8')
            spid = subprocess.check_output(['git', 'patch-id', '--stable'],
                    stdin=ps.stdout).decode('utf-8', errors='ignore')
            patchid = spid.split(' ', 1)[0]

            # Do nothing if sha is in stable database
            sc.execute("select sha from commits where sha='%s'" % sha)
            found = sc.fetchone()
            if found:
                continue

            # Do nothing if sha is already in database
            c.execute("select sha from commits where sha='%s'" % sha)
            found = c.fetchone()
            if found:
                continue

            last = sha

            usha = search_usha(sha, description)
            changeid = parse_changeID(sha)

            c.execute('INSERT INTO commits(sha, usha, patchid,' \
                      'description, changeid) VALUES (?, ?, ?, ?, ?)',
                      (sha, usha, patchid, description, changeid))
    if last:
        c.execute("UPDATE tip set sha='%s' where ref=1" % last)

    conn.commit()
    conn.close()
    sconn.close()


def update_chromeosdb():
    """Updates the chromeosdb for all chromeos branches."""
    os.chdir(CHROMEOS_PATH)

    for branch in SUPPORTED_KERNELS:
        start = 'v%s' % branch
        cdb = chromeosdb(branch)
        sdb = stabledb(branch)
        bname = chromeos_branch(branch)

        print('Handling %s' % bname)

        try:
            conn = sqlite3.connect(cdb)
            conn.text_factory = str

            c = conn.cursor()
            c.execute('select sha from tip')
            sha = c.fetchone()
            conn.close()
            if sha and sha[0]:
                start = sha[0]
        except sqlite3.Error:
            createdb(cdb, make_downstream_table)

        subprocess.run(['git', 'checkout', bname])
        subprocess.run(['git', 'pull'])

        update_commits(start, cdb, sdb)

    os.chdir(WORKDIR)


if __name__ == '__main__':
    update_chromeosdb()
