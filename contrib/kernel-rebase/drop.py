#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Mark patches for drop based on data in configuration file"""

from __future__ import print_function
import sqlite3
import time
from common import rebasedb
from config import subject_droplist, sha_droplist, droplist


def NOW():
    """Return current time"""
    return int(time.time())


def do_drop(c, sha, reason, usha=None):
    """Mark patch identified by sha for drop with provided reason and possibly replacement SHA"""

    c.execute("select disposition from commits where sha is '%s'" % sha)
    found = c.fetchone()
    if found[0] != 'drop':
        print('Dropping SHA %s: %s' % (sha, reason))
        c.execute("UPDATE commits SET disposition=('drop') where sha='%s'" %
                  sha)
        c.execute("UPDATE commits SET reason=('%s') where sha='%s'" %
                  (reason, sha))
        c.execute("UPDATE commits SET updated=('%d') where sha='%s'" %
                  (NOW(), sha))
        if usha:
            c.execute("UPDATE commits SET usha=('%s') where sha='%s'" %
                      (usha, sha))


def handle_drops():
    """Handle all drops"""

    conn = sqlite3.connect(rebasedb)

    c = conn.cursor()
    c2 = conn.cursor()

    # Drop patches listed explicitly as to be dropped.
    # Only drop if the listed SHA is actually in the database.

    for sha, reason, usha in sha_droplist:
        c.execute("select sha from commits where sha is '%s'" % sha)
        if c.fetchone():
            do_drop(c2, sha, reason, usha=usha)

    # Drop all Android patches. We'll pick them up from the most recent version.

    c.execute('select sha, subject from commits')
    for (sha, desc) in c.fetchall():
        for prefix in subject_droplist:
            if desc.startswith(prefix):
                do_drop(c2, sha, 'android')

    conn.commit()

    # Now drop commits touching directories/files specified in droplist.

    c.execute('select sha from commits')
    for (_sha,) in c.fetchall():
        c.execute("select filename from files where sha is '%s'" % _sha)
        for (filename,) in c.fetchall():
            dropped = 0
            for (_dir, _reason) in droplist:
                if filename.startswith(_dir):
                    do_drop(c2, _sha, _reason)
                    dropped = 1
                    break
            if dropped:
                break

    conn.commit()

    # Try again. This time drop duplicates.
    # TODO: Needs work. This identifies revert/reapply wrongly as duplicates.

    dsha = []

    c.execute('select sha,patchid,disposition from commits')
    for (_sha, _patchid, _disposition,) in c.fetchall():
        if _disposition == 'drop':
            continue
        if _sha in dsha:
            continue
        c2.execute("select sha from commits where patchid is '%s'" % _patchid)
        for (__sha,) in c2.fetchall():
            if __sha in dsha:
                continue
            if _sha != __sha:
                do_drop(c2, __sha, 'duplicate')
                dsha.append(__sha)

    conn.commit()
    conn.close()

if __name__ == '__main__':
    handle_drops()
