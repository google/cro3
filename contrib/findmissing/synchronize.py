#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Setup module containing script to Synchronize kernel repositories + database.
"""

import logging
import os
import subprocess

import cloudsql_interface
import common
import gerrit_interface
import git_interface


UPSTREAM_KERNEL_METADATA = common.get_kernel_metadata(
    common.Kernel.linux_upstream
)
STABLE_KERNEL_METADATA = common.get_kernel_metadata(common.Kernel.linux_stable)
CHROME_KERNEL_METADATA = common.get_kernel_metadata(common.Kernel.linux_chrome)

gerrit_to_db_status_map = {
    gerrit_interface.GerritStatus.NEW: common.Status.OPEN,
    gerrit_interface.GerritStatus.ABANDONED: common.Status.ABANDONED,
    gerrit_interface.GerritStatus.MERGED: common.Status.MERGED,
}


def synchronize_upstream(upstream_kernel_metadata):
    """Synchronizes locally cloned repo with linux upstream remote."""
    destdir = common.get_kernel_absolute_path(upstream_kernel_metadata.path)
    repo = upstream_kernel_metadata.repo

    if not os.path.exists(destdir):
        logging.info("Cloning %s into %s", repo, destdir)
        clone = ["git", "clone", "-q", repo, destdir]
        subprocess.run(clone, check=True)
    else:
        logging.info("Pulling latest changes in %s into %s", repo, destdir)
        handler = git_interface.commitHandler(
            common.Kernel.linux_upstream, "master"
        )
        handler.pull()

    os.chdir(common.WORKDIR)


def synchronize_custom(kernel):
    """Synchronizes locally cloned repo with linux stable/chromeos remote."""

    metadata = common.get_kernel_metadata(kernel)
    destdir = common.get_kernel_absolute_path(metadata.path)
    upstream_destdir = common.get_kernel_absolute_path(common.UPSTREAM_PATH)
    repo = metadata.repo

    if not os.path.exists(destdir):
        logging.info("Cloning %s into %s", repo, destdir)
        clone = ["git", "clone", "-q", repo, destdir]
        subprocess.run(clone, check=True)

        os.chdir(destdir)
        for branch in metadata.branches:
            branch_name = metadata.get_kernel_branch(branch)

            logging.info(
                "Creating local branch %s in destdir %s", branch_name, destdir
            )
            checkout_branch = ["git", "checkout", "-q", branch_name]
            subprocess.run(checkout_branch, check=True)

        logging.info(
            "Add remote upstream %s to destdir %s", upstream_destdir, destdir
        )
        add_upstream_remote = [
            "git",
            "remote",
            "add",
            "upstream",
            upstream_destdir,
        ]
        fetch_upstream = ["git", "fetch", "-q", "upstream"]
        subprocess.run(add_upstream_remote, check=True)
        subprocess.run(fetch_upstream, check=True)
        os.chdir(common.WORKDIR)
    else:
        logging.info("Updating %s into %s", repo, destdir)

        handler = git_interface.commitHandler(kernel)
        handler.fetch()
        handler.fetch("upstream")
        for branch in metadata.branches:
            branch_name = metadata.get_kernel_branch(branch)
            logging.info(
                "Updating local branch %s in destdir %s", branch_name, destdir
            )
            handler.pull(branch)


def setup_linux_chrome_git_hooks():
    """Setup git hooks for chromeos remote."""
    metadata = common.get_kernel_metadata(common.Kernel.linux_chrome)
    dest = os.path.join(
        common.get_kernel_absolute_path(metadata.path),
        ".git",
        "hooks",
        "commit-msg",
    )
    commit_msg = os.path.join(common.WORKSPACE_PATH, "git-hooks", "commit-msg")

    if not os.path.islink(dest):
        logging.info("Adding symlink %s to %s", dest, commit_msg)
        os.symlink(commit_msg, dest)


def synchronize_repositories(local=False):
    """Deep clones linux_upstream, linux_stable, and linux_chromeos repositories"""
    synchronize_upstream(UPSTREAM_KERNEL_METADATA)
    synchronize_custom(common.Kernel.linux_stable)
    synchronize_custom(common.Kernel.linux_chrome)
    setup_linux_chrome_git_hooks()
    if local:
        synchronize_custom(common.Kernel.linux_stable_rc)


def synchronize_databases():
    """Synchronizes the databases for upstream, stable, and chromeos."""
    with common.connect_db() as db:
        common.update_kernel_db(db, UPSTREAM_KERNEL_METADATA)
        common.update_kernel_db(db, STABLE_KERNEL_METADATA)
        common.update_kernel_db(db, CHROME_KERNEL_METADATA)


def synchronize_fixes_tables_with_gerrit():
    """Synchronizes the state of all OPEN/ABANDONED CL's with Gerrit."""
    with common.connect_db() as db, db.cursor() as c:
        # Find all OPEN/ABANDONED CL's in chrome_fixes
        fixes_tables = ["stable_fixes", "chrome_fixes"]

        for fixes_table in fixes_tables:
            q = f"""SELECT branch, fix_change_id
                    FROM {fixes_table}
                    WHERE (status = 'OPEN' OR status = 'ABANDONED')
                    AND fix_change_id IS NOT NULL"""
            c.execute(q)

            while True:
                rows = c.fetchmany(1000)
                if not rows:
                    break

                for branch, fix_change_id in rows:
                    gerrit_status = gerrit_interface.get_status(
                        fix_change_id, branch
                    )
                    status = gerrit_to_db_status_map[gerrit_status]
                    cloudsql_interface.update_change_status(
                        db, fixes_table, branch, fix_change_id, status
                    )


if __name__ == "__main__":
    synchronize_repositories()
    synchronize_databases()
