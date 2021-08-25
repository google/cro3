# -*- coding: utf-8 -*-"
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common functions and variables used by rebase scripts"""

import os
import sys
import re
import sqlite3
import subprocess

from config import datadir, rebasedb_name
from config import rebase_baseline_branch, rebase_target
from config import next_repo, stable_repo, android_repo

data_subdir = 'data'
if datadir is None:
    datadir = os.path.join(sys.path[0], data_subdir)

if rebasedb_name is None:
    rebasedb_name = 'rebase-%s.db' % rebase_target

repodir = 'repositories'

chromeos_path = os.path.join(datadir, repodir, 'linux-chrome')
upstream_path = os.path.join(datadir, repodir, 'linux-upstream')
stable_path = os.path.join(datadir, repodir, 'linux-stable') if stable_repo else None
android_path = os.path.join(datadir, repodir, 'linux-android') if android_repo else None
next_path = os.path.join(datadir, repodir, 'linux-next') if next_repo else None

dbdir = os.path.join(datadir, 'database')
rebasedb = os.path.join(dbdir, rebasedb_name)
upstreamdb = os.path.join(dbdir, 'upstream.db')
nextdb = os.path.join(dbdir, 'next.db') if next_repo else None

# This path must be relative to the root of the project
executor_io = os.path.join(data_subdir, 'executor_io')

def do_check_output(cmd):
    """Python version independent implementation of 'subprocess.check_output'"""

    return subprocess.check_output(cmd, stderr=subprocess.DEVNULL, # pylint: disable=no-member
                                   encoding='utf-8', errors='ignore')


def stable_baseline():
    """Return most recent label in to-be-rebased branch"""

    if not os.path.exists(chromeos_path):
        return None

    cmd = ['git', '-C', chromeos_path, 'describe', rebase_baseline_branch]
    tag = do_check_output(cmd)
    return tag.split('-')[0]


def rebase_baseline():
    """Return most recent tag in to-be-rebased branch"""

    baseline = stable_baseline()
    if baseline:
        return baseline.split('.')[0] + '.' + baseline.split('.')[1]
    return None


version_re = re.compile(r'(v[0-9]+(\.[0-9]+)(-rc[0-9]+(-dontuse)?)?)\s*')


def rebase_target_tag():
    """Return most recent label in upstream kernel"""

    if not os.path.exists(upstream_path):
        return 'HEAD'

    if rebase_target == 'latest':
        cmd = ['git', '-C', upstream_path, 'describe']
        tag = do_check_output(cmd)
        v = version_re.match(tag)
        if v:
            tag = v.group(0).strip('\n')
        else:
            tag = 'HEAD'
    else:
        tag = rebase_target

    return tag


def rebase_target_version():
    """Return target version for rebase"""
    return rebase_target_tag().strip('v')


def stable_branch(version):
    """Return stable branch name in upstream stable kernel"""
    return 'linux-%s.y' % version


def chromeos_branch(version):
    """Return chromeos branch name"""
    return 'chromeos-%s' % version


def doremove(filename):
    """remove file if it exists"""

    try:
        os.remove(filename)
    except OSError:
        pass


def createdb(db, op):
    """remove and recreate database"""

    dbdirname = os.path.dirname(db)
    if not os.path.exists(dbdirname):
        os.mkdir(dbdirname)

    doremove(db)

    conn = sqlite3.connect(db)
    c = conn.cursor()

    op(c)

    # Convention: table 'tip' ref 1 contains the most recently processed SHA.
    # Use this to avoid re-processing SHAs already in the database.
    c.execute('CREATE TABLE tip (ref integer, sha text)')
    c.execute('INSERT INTO tip (ref, sha) VALUES (?, ?)', (1, ''))

    # Save (commit) the changes
    conn.commit()
    conn.close()


# match "vX.Y[.Z][.rcN]"
_version_re = re.compile(r'(v[0-9]+(?:\.[0-9]+)+(?:-rc[0-9]+(-dontuse)?)?)\s*')


def get_integrated_tag(sha):
    """For a given SHA, find the first tag that includes it."""

    try:
        cmd = [
            'git', '-C', upstream_path, 'describe', '--match', 'v*',
            '--contains', sha
        ]
        tag = do_check_output(cmd)
        return _version_re.match(tag).group()
    except AttributeError:
        return None
    except subprocess.CalledProcessError:
        return None


# extract_numerics matches numeric parts of a Linux version as separate elements
# For example, "v5.4" matches "5" and "4", and "v5.4.12" matches "5", "4", and "12"
extract_numerics = re.compile(
    r'(?:v)?([0-9]+)\.([0-9]+)(?:\.([0-9]+))?(?:-rc([0-9]+))?\s*')


def version_to_number(version):
    """Convert Linux version to numeric value usable for comparisons.

    A branch with higher version number will return a larger number.
    Supports version numbers up to 999, and release candidates up to 99.

    Returns 0 if the kernel version can not be extracted.
    """

    m = extract_numerics.match(version)
    if m:
        major = int(m.group(1))
        minor1 = int(m.group(2))
        minor2 = int(m.group(3)) if m.group(3) else 0
        minor3 = int(m.group(4)) if m.group(4) else 0
        total = major * 1000000000 + minor1 * 1000000 + minor2 * 1000
        if minor3 != 0:
            total -= (100 - minor3)
        return total
    return 0


def version_compare(v1, v2):
    """Convert linux version into numberic string for comparison"""
    return version_to_number(v2) >= version_to_number(v1)


def is_in_baseline(version, baseline=rebase_baseline()):
    """Return true if 1st version is included in the current baseline.

    If no baseline is provided, use default.
    """

    if version and baseline:
        return version_compare(version, baseline)

    # If there is no version tag, it can not be included in any baseline.
    return False


def is_in_target(version, target=rebase_target_tag()):
    """Return true if 1st version is included in the current baseline.

    If no baseline is provided, use default.
    """

    if version and target:
        return version_compare(version, target)

    # If there is no version tag, it can not be included in any target.
    return False
