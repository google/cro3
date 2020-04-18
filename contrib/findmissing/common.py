#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing shared helper methods."""

from __future__ import print_function
import logging
import os
import re
import time
from enum import Enum
import subprocess
import MySQLdb

import initdb_upstream
import initdb_stable
import initdb_chromeos


KERNEL_SITE = 'https://git.kernel.org/'
UPSTREAM_REPO = KERNEL_SITE + 'pub/scm/linux/kernel/git/torvalds/linux'
STABLE_REPO = KERNEL_SITE + 'pub/scm/linux/kernel/git/stable/linux-stable'
STABLE_RC_REPO = KERNEL_SITE + 'pub/scm/linux/kernel/git/stable/linux-stable-rc'

CHROMIUM_SITE = 'https://chromium.googlesource.com/'
CHROMEOS_KERNEL_DIR = 'chromiumos/third_party/kernel'
CHROMEOS_REPO = os.path.join(CHROMIUM_SITE, CHROMEOS_KERNEL_DIR)
CHROMIUM_REVIEW_BASEURL = 'https://chromium-review.googlesource.com/a'

# Order BRANCHES from oldest to newest
CHROMEOS_BRANCHES = ['4.4', '4.14', '4.19', '5.4']
STABLE_BRANCHES = ['4.4', '4.9', '4.14', '4.19', '5.4', '5.6']

UPSTREAM_START_BRANCH = 'v%s' % CHROMEOS_BRANCHES[0]

CHROMEOS_PATH = 'linux_chrome'
STABLE_PATH = 'linux_stable'
STABLE_RC_PATH = 'linux_stable_rc'
UPSTREAM_PATH = 'linux_upstream'

WORKDIR = os.getcwd()
HOMEDIR = os.path.expanduser('~')
GCE_GIT_COOKIE_PATH = os.path.join(HOMEDIR, '.git-credential-cache/cookie')
LOCAL_GIT_COOKIE_PATH = os.path.join(HOMEDIR, '.gitcookies')


class Status(Enum):
    """Text representation of database enum to track status of gerrit CL."""
    OPEN = 1 # Gerrit ticket was created for clean fix patch
    MERGED = 2 # Gerrit ticket was merged and closed
    ABANDONED = 3 # Gerrit ticket was abandoned
    CONFLICT = 4 # Gerrit ticket NOT created since patch doesn't apply properly


class Kernel(Enum):
    """Enum representing which Kernel we are representing."""
    linux_stable = 1
    linux_stable_rc = 2
    linux_chrome = 3
    linux_upstream = 4


class KernelMetadata(object):
    """Object to group kernel Metadata."""
    path = None
    repo = None
    kernel_fixes_table = None
    branches = None
    tag_template = None
    get_kernel_branch = None
    update_table = None

    def __init__(self, _path, _repo, _kernel_fixes_table, _branches, _tag_template,
            _get_kernel_branch, _update_table):
        self.path = _path
        self.repo = _repo
        self.kernel_fixes_table = _kernel_fixes_table
        self.branches = _branches
        self.tag_template = _tag_template
        self.get_kernel_branch = _get_kernel_branch
        self.update_table = _update_table


def get_current_time():
    """Returns DATETIME in specific time format required by SQL."""
    return time.strftime('%Y-%m-%d %H:%M%:%S')


def stable_branch(version):
    """Stable branch name"""
    return 'linux-%s.y' % version


def chromeos_branch(version):
    """Chromeos branch name"""
    return 'chromeos-%s' % version


def search_upstream_sha(kernel_sha):
    """Search for upstream sha that kernel_sha is cherry-picked from.

    If found, return upstream_sha, otherwise return None.
    """
    usha = None
    desc = subprocess.check_output(['git', 'show', '-s', kernel_sha],
                                        encoding='utf-8', errors='ignore')

    # "commit" is sometimes seen multiple times, such as with commit 6093aabdd0ee
    m = re.findall(r'cherry picked from (?:commit )+([0-9a-f]+)', desc, re.M)
    if not m:
        m = re.findall(r'^\s*(?:commit )+([a-f0-9]+) upstream', desc, re.M)
        if not m:
            m = re.findall(r'^\s*\[\s*Upstream (?:commit )+([0-9a-f]+)\s*\]', desc, re.M)
    if m:
        # The patch may have been picked multiple times; only record the last entry.
        usha = m[-1]
        return usha[:12]
    return usha


def patch_link(changeID):
    """Link to patch on gerrit"""
    return 'https://chromium-review.googlesource.com/q/%s' % changeID


def update_previous_fetch(db, kernel, branch, last_sha):
    """Updates the previous_fetch table for a kernel branch."""
    c = db.cursor()
    q = """UPDATE previous_fetch
            SET sha_tip = %s
            WHERE linux = %s AND branch = %s"""
    c.execute(q, [last_sha, kernel.name, branch])

    db.commit()


def get_kernel_absolute_path(repo_name):
    """Returns absolute path to kernel repositories"""
    return os.path.join(HOMEDIR, 'kernel_repositories', repo_name)


def update_kernel_db(db, kernel_metadata):
    """Update (upstream/stable/chrome) previous_fetch, fixes and commits SQL tables."""
    path = kernel_metadata.path
    os.chdir(get_kernel_absolute_path(path))

    for branch in kernel_metadata.branches:
        start = kernel_metadata.tag_template % branch

        logging.info('Handling %s', kernel_metadata.get_kernel_branch(branch))

        try:
            c = db.cursor()
            q = """SELECT sha_tip
                    FROM previous_fetch
                    WHERE linux = %s AND branch = %s"""
            c.execute(q, [path, branch])
            sha = c.fetchone()
            if sha and sha[0]:
                start = sha[0]
            else:
                q = """INSERT INTO previous_fetch (linux, branch, sha_tip)
                        VALUES (%s, %s, %s)"""
                c.execute(q, [path, branch, start])
        except MySQLdb.Error as e: # pylint: disable=no-member
            logging.error('Make sure the tables have been initialized in \
                           ./scripts/sql/initialize_sql_tables.sql')
            raise e


        kernel_metadata.update_table(branch, start, db)
        db.commit()

    os.chdir(WORKDIR)


def get_kernel_metadata(kernel):
    """Returns KernelMetadata for each Kernel Enum"""
    stable_kernel_metadata = KernelMetadata(STABLE_PATH, STABLE_REPO, 'stable_fixes',
            STABLE_BRANCHES, 'v%s', stable_branch, initdb_stable.update_stable_table)
    stable_rc_kernel_metadata = KernelMetadata(STABLE_RC_PATH, STABLE_RC_REPO, 'stable_fixes',
            STABLE_BRANCHES, 'v%s', stable_branch, initdb_stable.update_stable_table)
    chrome_kernel_metadata = KernelMetadata(CHROMEOS_PATH, CHROMEOS_REPO, 'chrome_fixes',
            CHROMEOS_BRANCHES, 'v%s', chromeos_branch, initdb_chromeos.update_chrome_table)
    upstream_kernel_metadata = KernelMetadata(UPSTREAM_PATH, UPSTREAM_REPO, 'upstream_fixes',
            [UPSTREAM_START_BRANCH], '%s', lambda *args: 'master',
            initdb_upstream.update_upstream_table)

    kernel_metadata_lookup = {
            Kernel.linux_stable: stable_kernel_metadata,
            Kernel.linux_stable_rc: stable_rc_kernel_metadata,
            Kernel.linux_chrome: chrome_kernel_metadata,
            Kernel.linux_upstream: upstream_kernel_metadata
    }

    try:
        return kernel_metadata_lookup[kernel]
    except KeyError as e:
        raise KeyError('Conditionals should match Kernel Enum types.', e)
