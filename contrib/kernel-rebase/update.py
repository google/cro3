#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Update rebase database with new information from upstream and next database"""

from __future__ import print_function

import re
import sqlite3

from common import nextdb
from common import rebasedb
from common import upstreamdb


subject = re.compile(
    "(ANDROID: *|CHROMIUM: *|CHROMEOS: *|UPSTREAM: *|FROMGIT: *|FROMLIST: *|BACKPORT: *)*(.*)"
)


def findsha(uconn, sha, patchid, desc):
    """Try to find matching SHA in provided database.

    Return updated SHA, or None if not found.
    """

    c = uconn.cursor()

    if sha is not None:
        c.execute("select sha from commits where sha is '%s'" % sha)
        usha = c.fetchone()
        if usha:
            # print("  Found SHA %s in upstream database" % usha)
            return usha[0]

    # Now look for patch id if provided
    if patchid is not None:
        c.execute("select sha from commits where patchid is '%s'" % patchid)
        usha = c.fetchone()
        if usha:
            # print("  Found SHA %s in upstream database based on patch ID" % usha)
            return usha[0]

    # The SHA is not upstream, or not known at all.
    # See if we can find the commit subject.
    s = subject.search(desc)
    if s:
        sdesc = s.group(2).replace("'", "''")
        c.execute("select sha from commits where subject is '%s'" % sdesc)
        usha = c.fetchone()
        if usha:
            # print("  Found upstream SHA '%s' based on subject line" % usha)
            return usha[0]

    return None


def update_commits():
    """Validate 'usha' field in rebase database.

    Verify if the upstream SHA actually exists by looking it up in the upstream
    database. If it doesn't exist, and if a matching commit is not found either,
    remove it.
    """

    conn = sqlite3.connect(rebasedb)
    uconn = sqlite3.connect(upstreamdb)
    nconn = sqlite3.connect(nextdb) if nextdb else None
    c = conn.cursor()

    c.execute("select sha, usha, patchid, subject from commits")
    for (sha, usha, patchid, desc) in c.fetchall():
        uusha = findsha(uconn, usha, patchid, desc)
        # if it is not in the upstream database, maybe it is in -next.
        # Try to pick it up from there.
        if uusha is None and nconn:
            uusha = findsha(nconn, usha, None, desc)
        if not uusha:
            uusha = ""
        if usha != uusha:
            print("SHA '%s': Updating usha '%s' with '%s'" % (sha, usha, uusha))
            c.execute(
                "UPDATE commits set usha='%s' where sha='%s'" % (uusha, sha)
            )

    conn.commit()
    conn.close()
    uconn.close()
    if nconn:
        nconn.close()


if __name__ == "__main__":
    update_commits()
