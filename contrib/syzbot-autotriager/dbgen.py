#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Local cache generator for syzbot-autotriager."""

from __future__ import print_function

import argparse
import os
import subprocess
import sys
import tempfile

import git
import issuetracker
import simpledb
import syzweb

import config


def fetch_it(hotlistid):
    """Uses Issuetracker to fetch bugs from a specific |hotlistid|."""
    b = issuetracker.Issuetracker(hotlistid)
    b.save()


def fetch_commits():
    """Uses Gitlog to fetch and cache commits from various kernels."""
    dbs = (
        config.SRC_LINUX_DB,
        config.SRC_V414_DB,
        config.SRC_V44_DB,
        config.SRC_V318_DB,
        config.SRC_V314_DB,
        config.SRC_V310_DB,
        config.SRC_V38_DB,
        config.SRC_LINUX_STABLE_414_DB,
        config.SRC_LINUX_STABLE_44_DB,
    )

    tfiles = [tempfile.NamedTemporaryFile() for _ in xrange(len(dbs))]

    env = os.environ.copy()
    env.update({"TFILE_%d" % (i): tfile.name for i, tfile in enumerate(tfiles)})

    try:
        env["CROS_ROOT"] = os.path.expanduser(config.CROS_ROOT)
        env["LINUX"] = os.path.expanduser(config.LINUX)
        env["LINUXSTABLE"] = os.path.expanduser(config.LINUX_STABLE)

        subprocess.check_call(["./dump_git_log.sh"], env=env)

        for tfile, dbname in zip(tfiles, dbs):
            g = git.Gitlog(filename=tfile.name, dbname=dbname)
            g.save()

    finally:
        for f in tfiles:
            f.close()


def fetch_syzweb():
    """Uses SyzkallerWeb to fetch and cache info from syzkaller.appspot.com."""
    sw = syzweb.SyzkallerWeb()
    sw.save()


def get_parser():
    """Create and return an ArgumentParser instance."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--it",
        type=str,
        dest="hotlistid",
        help="fetch all bugs from issuetracker and cache them " "locally",
    )
    parser.add_argument(
        "--commits",
        action="store_true",
        help="fetch all commits from various git "
        "repositories and cache them locally",
    )
    parser.add_argument(
        "--syzweb",
        action="store_true",
        help="fetch all fixes from syzkaller.appspot.com "
        "and cache them locally",
    )
    parser.add_argument(
        "--fetchall",
        action="store_true",
        help="equivalent of --it[HOTLISTID] --commits --syzweb",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list the number of records in each local cache",
    )
    return parser


def main(argv):
    """main."""
    parser = get_parser()
    opts = parser.parse_args(argv)

    if opts.fetchall or opts.hotlistid:
        if not opts.hotlistid:
            parser.error("No HOTLISTID provided")
            return 1
        fetch_it(opts.hotlistid)

    if opts.fetchall or opts.commits:
        print("[+] Fetching commits")
        fetch_commits()

    if opts.fetchall or opts.syzweb:
        print("[+] Fetching syzweb issues")
        fetch_syzweb()

    if opts.list:
        nodb = True
        for db in (
            config.ISSUETRACKER_DB,
            config.SYZWEB_DB,
            config.SRC_LINUX_DB,
            config.SRC_V414_DB,
            config.SRC_V44_DB,
            config.SRC_V318_DB,
            config.SRC_V314_DB,
            config.SRC_V310_DB,
            config.SRC_V38_DB,
        ):
            if not os.path.exists(db):
                continue
            nodb = False
            s = simpledb.SimpleDB(db)
            print("[+] %s found with %d records" % (db, s.count()))
        print("[x] No local caches found" if nodb else "")

    if not (
        opts.hotlistid
        or opts.commits
        or opts.syzweb
        or opts.fetchall
        or opts.list
    ):
        parser.error("No options selected")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
