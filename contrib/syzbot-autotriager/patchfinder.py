#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Find patches that are missing from stable kernels."""

from __future__ import print_function

import argparse
import base64
import os
import sys

import simpledb

import config
import utils


class PatchFinderException(Exception):
    """Exceptions raised by PatchFinder."""


class PatchFinder(object):
    """PatchFinder locates patches that are absent in stable kernels."""

    DEFAULTS = {
        "414": (config.SRC_LINUX_STABLE_414_DB, "linux-4.14.y"),
        "44": (config.SRC_LINUX_STABLE_44_DB, "linux-4.4.y"),
    }

    def __init__(self, kver, objfiles):
        self.kver = kver
        self.dbname, self.branch = PatchFinder.DEFAULTS[self.kver]

        self.assert_dbs_exist()

        self.db = simpledb.SimpleDB(self.dbname)
        self.mainline = simpledb.SimpleDB(config.SRC_LINUX_DB)

        contents = open(os.path.expanduser(objfiles)).readlines()
        objfiles = [i.strip() for i in contents]
        self.srcfiles = [i[2:-2] + ".c" for i in objfiles if i.endswith(".o")]
        self.stats = {}

    def assert_dbs_exist(self):
        "Check if caches exist, else raise PatchFinderException." ""
        if not os.path.isfile(self.dbname):
            raise PatchFinderException(
                "%s not found, create with dbgen.py" % (self.dbname)
            )

        if not os.path.isfile(config.SRC_LINUX_DB):
            raise PatchFinderException(
                "%s not found, create with dbgen.py" % (config.SRC_LINUX_DB)
            )

    def commit_in_stable(self, title):
        """Returns true if |title| is a commit present in stable."""
        stable_commit = self.db.find_one(title=title)
        if not stable_commit:
            return False
        return True

    def commit_is_interesting(self, files):
        """Returns true if a in |files| is used in a kernel build."""
        return any(i in files for i in self.srcfiles)

    def process(self):
        """PatchFinder core."""
        print("Mainline commit count=%d" % (self.mainline.count()))
        commits = self.mainline.all()

        for counter, commit in enumerate(commits):
            if (counter + 1) % 100000 == 0:
                print("--- %d" % (counter + 1))

            body, files = (
                base64.b64decode(i) for i in [commit["body"], commit["files"]]
            )
            files = [i for i in files.splitlines() if i]

            if not utils.interesting_keyword_in(body):
                continue

            if self.commit_in_stable(commit["title"]):
                utils.incstats(self.stats, "commit_already_in_stable")
                continue

            if not self.commit_is_interesting(files):
                utils.incstats(self.stats, "commit_is_not_interesting")
                continue

            causer = utils.fixes_stmt(body)
            if not causer:
                continue

            cstr = utils.commitstr(causer)
            if not cstr:
                utils.incstats(self.stats, "fixes_stmt_unparseable")
                continue

            if not self.commit_in_stable(cstr):
                utils.incstats(self.stats, "root_cause_present")
                continue

            print(
                'Missing commit: %s ("%s")'
                % (commit["commitid"][:10], commit["title"])
            )
            utils.incstats(self.stats, "count")

    def dump_stats(self):
        """Print stats related to missing commits."""
        print(self.stats)


def get_parser():
    """Create and return an ArgumentParser instance."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--kver",
        type=str,
        required=True,
        choices=["414", "44"],
        help="Choose one of supported kernel versions",
    )
    parser.add_argument(
        "--objfiles",
        type=str,
        required=True,
        help="objfiles to use for filtering results",
    )
    return parser


def main(argv):
    """main."""
    parser = get_parser()
    opts = parser.parse_args(argv)

    p = PatchFinder(opts.kver, opts.objfiles)

    p.process()
    p.dump_stats()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
