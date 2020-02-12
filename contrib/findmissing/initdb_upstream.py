#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module parses and stores mainline linux patches to be easily accessible."""

from __future__ import print_function
import os
import re
import sqlite3
import subprocess

from common import WORKDIR, UPSTREAMDB, createdb, UPSTREAM_PATH, SUPPORTED_KERNELS


UPSTREAM_BASE = 'v' + SUPPORTED_KERNELS[0]

RF = re.compile(r'^\s*Fixes: (?:commit )*([0-9a-f]+).*')
RDESC = re.compile(r'.* \("([^"]+)"\).*')


def make_tables(c):
    """Initializes the upstreamdb tables."""
    # Upstream commits
    c.execute('CREATE TABLE commits (sha text, description text)')
    c.execute('CREATE UNIQUE INDEX commit_sha ON commits (sha)')

    # Fixes associated with upstream commits. sha is the commit, fsha is its fix.
    # Each sha may have multiple fixes associated with it.
    c.execute('CREATE TABLE fixes \
                        (sha text, fsha text, patchid text, ignore integer)')
    c.execute('CREATE INDEX sha ON fixes (sha)')


def handle(start):
    """Parses git logs and builds upstreamdb tables."""
    conn = sqlite3.connect(UPSTREAMDB)
    conn.text_factory = str
    c = conn.cursor()
    c2 = conn.cursor()

    commits = subprocess.check_output(['git', 'log', '--abbrev=12', '--oneline',
                                       '--no-merges', '--reverse', start+'..'])
    for commit in commits.decode('utf-8').splitlines():
        if commit != '':
            elem = commit.split(' ', 1)
            sha = elem[0]
            last = sha

            # skip if SHA is already in database. This will happen
            # for the first SHA when the script is re-run.
            c.execute("select sha from commits where sha is '%s'" % sha)
            if c.fetchone():
                continue

            description = elem[1].rstrip('\n')
            c.execute('INSERT INTO commits(sha, description) VALUES (?, ?)',
                                (sha, description))
            # check if this patch fixes a previous patch.
            subprocess_cmd = ['git', 'show', '-s', '--pretty=format:%b', sha]
            description = subprocess.check_output(subprocess_cmd).decode('utf-8')
            for d in description.splitlines():
                m = RF.search(d)
                fsha = None
                if m and m.group(1):
                    try:
                        # Normalize fsha to 12 characters
                        cmd = 'git show -s --pretty=format:%%H %s' % m.group(1)
                        fsha = subprocess.check_output(cmd.split(' '),
                                stderr=subprocess.DEVNULL).decode('utf-8')
                    except subprocess.CalledProcessError:
                        print("Commit '%s' for SHA '%s': "
                                'Not found' % (m.group(0), sha))
                        m = RDESC.search(d)
                        if m:
                            desc = m.group(1)
                            desc = desc.replace("'", "''")
                            c2.execute('select sha from commits where '
                                    "description is '%s'" % desc)
                            fsha = c2.fetchone()
                            if fsha:
                                fsha = fsha[0]
                                print("  Real SHA may be '%s'" % fsha)
                        # The Fixes: tag may be wrong. The sha may not be in the
                        # upstream kernel, or the format may be completely wrong
                        # and m.group(1) may not be a sha in the first place.
                        # In that case, do nothing.
                if fsha:
                    print('Commit %s fixed by %s' % (fsha[0:12], sha))
                    # Calculate patch ID for fixing commit.
                    ps = subprocess.Popen(['git', 'show', sha],
                            stdout=subprocess.PIPE)
                    spid = subprocess.check_output(['git', 'patch-id'],
                            stdin=ps.stdout).decode('utf-8', errors='ignore')
                    patchid = spid.split(' ', 1)[0]

                    # Insert in reverse order: sha is fixed by fsha.
                    # patchid is the patch ID associated with fsha (in the db).
                    c.execute('INSERT into fixes (sha, fsha, patchid, ignore) '
                            'VALUES (?, ?, ?, ?)',
                            (fsha[0:12], sha, patchid, 0))

    if last:
        c.execute("UPDATE tip set sha='%s' where ref=1" % last)

    conn.commit()
    conn.close()


def update_upstreamdb():
    """Updates the upstreamdb database."""
    start = UPSTREAM_BASE

    try:
        # see if we previously handled anything. If yes, use it.
        # Otherwise re-create database
        conn = sqlite3.connect(UPSTREAMDB)
        conn.text_factory = str
        c = conn.cursor()
        c.execute('select sha from tip')
        sha = c.fetchone()
        conn.close()
        if sha and sha[0] != '':
            start = sha[0]
    except sqlite3.Error:
        createdb(UPSTREAMDB, make_tables)

    os.chdir(UPSTREAM_PATH)
    subprocess.check_output(['git', 'pull'])

    handle(start)

    os.chdir(WORKDIR)


if __name__ == '__main__':
    update_upstreamdb()
