#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing shared helper methods."""

from __future__ import print_function
import os
import re
from enum import Enum
import MySQLdb

import initdb_upstream
import initdb_stable
import initdb_chromeos


KERNEL_SITE = 'https://git.kernel.org/'
UPSTREAM_REPO = KERNEL_SITE + 'pub/scm/linux/kernel/git/torvalds/linux'
STABLE_REPO = KERNEL_SITE + 'pub/scm/linux/kernel/git/stable/linux-stable'

CHROMIUM_SITE = 'https://chromium.googlesource.com/'
CHROMEOS_REPO = CHROMIUM_SITE + 'chromiumos/third_party/kernel'
CHROMIUM_REVIEW_BASEURL = 'https://chromium-review.googlesource.com/'

# Order SUPPORTED_KERNELS from oldest to newest
SUPPORTED_KERNELS = ('4.4', '4.14', '4.19', '5.4')
UPSTREAM_START_TAG = 'v%s' % SUPPORTED_KERNELS[0]

CHROMEOS_PATH = 'linux_chrome'
STABLE_PATH = 'linux_stable'
UPSTREAM_PATH = 'linux_upstream'

WORKDIR = os.getcwd()

# "commit" is sometimes seen multiple times, such as with commit 6093aabdd0ee
CHERRYPICK = re.compile(r'cherry picked from (commit )+([0-9a-f]+)')
STABLE = re.compile(r'^\s*(commit )+([a-f0-9]+) upstream')
STABLE2 = re.compile(r'^\s*\[\s*Upstream (commit )+([0-9a-f]+)\s*\]')


class Status(Enum):
    """Text representation of database enum to track status of gerrit CL."""
    OPEN = 1 # Gerrit ticket was created for clean fix patch
    MERGED = 2 # Gerrit ticket was merged and closed
    ABANDONED = 3 # Gerrit ticket was abandoned
    CONFLICT = 4 # Gerrit ticket NOT created since patch doesn't apply properly


class Kernel(Enum):
    """Enum representing which Kernel we are representing."""
    linux_stable = 1
    linux_chrome = 2
    linux_upstream = 3


class KernelMetadata(object):
    """Object to group kernel Metadata."""
    local_kernel_path = None
    kernel_table = None
    kernel_fixes_table = None
    get_kernel_branch = None

    def __init__(self, _local_path, _kernel_table, _kernel_fixes_table,
            _get_kernel_branch):
        self.local_kernel_path = _local_path
        self.kernel_table = _kernel_table
        self.kernel_fixes_table = _kernel_fixes_table
        self.get_kernel_branch = _get_kernel_branch


def stable_branch(version):
    """Stable branch name"""
    return 'linux-%s.y' % version


def chromeos_branch(version):
    """Chromeos branch name"""
    return 'chromeos-%s' % version


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


def update_kernel_db(db, kernel):
    """Update (upstream/stable/chrome) previous_fetch, fixes and commits SQL tables."""
    get_branch_name = start = update_commits = None

    if kernel == Kernel.linux_chrome:
        get_branch_name = chromeos_branch
        update_commits = initdb_chromeos.update_chrome_table
    elif kernel == Kernel.linux_stable:
        get_branch_name = stable_branch
        update_commits = initdb_stable.update_stable_table
    else:
        get_branch_name = lambda *args: 'master'
        update_commits = initdb_upstream.update_upstream_table

    path = kernel.name
    branches = [UPSTREAM_START_TAG] if kernel == Kernel.linux_upstream else SUPPORTED_KERNELS
    start_template = '%s' if kernel == Kernel.linux_upstream else 'v%s'

    os.chdir(path)

    for branch in branches:
        start = start_template % branch

        print('Handling %s' % get_branch_name(branch))

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
            print('Make sure the tables have been initialized in \
                    ./scripts/sql/initialize_sql_tables.sql', e)


        update_commits(branch, start, db)

    os.chdir(WORKDIR)

def get_kernel_metadata(release):
    """Returns KernelMetadata for a release (linux-stable, or linux-chrome"""
    kernel_metadata = None
    if release == Kernel.linux_stable:
        kernel_metadata = KernelMetadata(STABLE_PATH, 'linux_stable',
                'stable_fixes', stable_branch)
    elif release == Kernel.linux_chrome:
        kernel_metadata = KernelMetadata(CHROMEOS_PATH, 'linux_chrome',
                'chrome_fixes', chromeos_branch)
    elif release == Kernel.linux_upstream:
        kernel_metadata = KernelMetadata(UPSTREAM_PATH, 'linux_upstream_commits',
                'linux_upstream_fixes', None)
    else:
        raise ValueError('Conditionals should match Kernel Enum release types.')
    return kernel_metadata
