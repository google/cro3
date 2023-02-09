#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module rebuilding database with metadata about chromeos patches."""

import logging
import re
import subprocess

import common
import MySQLdb  # pylint: disable=import-error
import MySQLdb.constants.ER  # pylint: disable=import-error
import util


UPSTREAM = re.compile(r"(ANDROID: *|UPSTREAM: *|FROMGIT: *|BACKPORT: *)+(.*)")
CHROMIUM = re.compile(r"(CHROMIUM: *|FROMLIST: *)+(.*)")
CHANGEID = re.compile(r"^( )*Change-Id: [a-zA-Z0-9]*$")


def update_chrome_table(branch, start, db):
    """Updates the linux chrome commits table.

    Also keep a reference of last parsed SHA so we don't have to index the
        entire commit log on each run.
    Skip commit if it is contained in the linux stable db, add to linux_chrome
    """
    logging.info("Linux chrome on branch %s", branch)
    cursor = db.cursor()

    logging.info("Pulling all the latest linux chrome commits")
    subprocess.check_output(["git", "checkout", common.chromeos_branch(branch)])
    subprocess.check_output(["git", "pull"])

    logging.info("Loading all linux chrome commit logs from %s", start)
    cmd = [
        "git",
        "log",
        "--no-merges",
        "--abbrev=12",
        "--oneline",
        "--reverse",
        "%s.." % start,
    ]
    commits = subprocess.check_output(cmd, encoding="utf-8", errors="ignore")

    last = None
    logging.info("Analyzing commits to build linux_chrome table.")

    for commit in commits.splitlines():
        if not commit:
            continue

        sha, description = commit.rstrip("\n").split(" ", 1)
        last = sha

        # Do nothing if sha is in linux_stable since we
        # don't want to duplicate tracking linux_stable sha's
        q = """SELECT 1 FROM linux_stable WHERE sha = %s"""
        cursor.execute(q, [sha])
        if cursor.fetchone():
            continue

        # Calculate patch ID
        patch_id = util.calc_patch_id(sha, stable=True)

        usha = None
        if not CHROMIUM.match(description):
            usha = common.search_upstream_sha(sha)

        try:
            q = """INSERT INTO linux_chrome
                    (sha, branch, upstream_sha, patch_id, description)
                    VALUES (%s, %s, %s, %s, %s)"""
            cursor.execute(q, [sha, branch, usha, patch_id, description])
            logging.info(
                "Insert into linux_chrome %s %s %s %s %s",
                sha,
                branch,
                usha,
                patch_id,
                description,
            )
        except MySQLdb.Error as e:  # pylint: disable=no-member
            # We'll see duplicates if the last commit handled previously was
            # the tip of a merge. In that case, all commits from the tail of
            # that merge up to the time when it was integrated will be handled
            # again. Let's ignore that situation.
            if e.args[0] != MySQLdb.constants.ER.DUP_ENTRY:
                logging.error(
                    "Error inserting [%s %s %s %s %s] into linux_chrome: error %d (%s)",
                    sha,
                    branch,
                    usha,
                    patch_id,
                    description,
                    e.args[0],
                    e.args[1],
                )
        except UnicodeDecodeError as e:
            logging.error(
                "Unicode error inserting [%s %s %s %s %s] into linux_chrome: error %s",
                sha,
                branch,
                usha,
                patch_id,
                description,
                e,
            )

    # Update previous fetch database
    if last:
        common.update_previous_fetch(
            db, common.Kernel.linux_chrome, branch, last
        )

    db.commit()


if __name__ == "__main__":
    with common.connect_db() as cloudsql_db:
        kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_chrome)
        common.update_kernel_db(cloudsql_db, kernel_metadata)
