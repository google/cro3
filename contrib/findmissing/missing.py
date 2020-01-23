#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Find missing stable and backported mainline fix patches in chromeos."""

from __future__ import print_function
import os
import subprocess
import sys
import sqlite3
import re
from enum import Enum

import config
from common import stabledb, UPSTREAMDB, \
     stable_branch, chromeosdb, chromeos_branch


CHANGEID = re.compile(r'^( )*Change-Id: [a-zA-Z0-9]*$')


class Path(Enum):
    """Enum representing repo path as Stable or ChromeOS."""
    stable = 1
    chromeos = 2


def get_status(sha):
    """Check if patch needs to be applied to current branch.

    The working directory and branch must be set when calling
    this function.

    Return 0 if the patch has already been applied,
    1 if the patch is missing and applies cleanly,
    2 if the patch is missing and fails to apply.
    """
    ret = 0

    cmd = 'git reset --hard HEAD'
    subprocess.run(cmd.split(' '), stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)

    try:
        # Returns 0 on success, else a non-zero status code
        result = subprocess.call(['git', 'cherry-pick', '-n', sha],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL)

        if result:
            ret = 2
        else:
            diff = subprocess.check_output(['git', 'diff', 'HEAD'])
            if diff:
                ret = 1
    except subprocess.CalledProcessError:
        ret = 2

    cmd = 'git reset --hard HEAD'
    subprocess.run(cmd.split(' '), stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL)


    return ret


def usha_to_downstream_sha(sdb, usha):
    """Retrieves chromeos/stable sha by indexing db.

    Returns sha or None if upstream sha doesn't exist downstream.
    """
    cs = sdb.cursor()
    cs.execute("SELECT sha from commits where usha is '%s'" % usha)
    row = cs.fetchone()

    return row[0] if row else None


def parse_changeID(chromeos_sha):
    """String searches for Change-Id in a chromeos git commit.

    Returns Change-Id or None if commit doesn't have associated Change-Id
    """
    commit = subprocess.check_output(['git', 'show', \
            chromeos_sha]).decode('utf-8', errors='ignore')

    for line in commit.splitlines():
        if CHANGEID.match(line):
            # removes whitespace prefixing Change-Id
            line = line.lstrip()
            commit_changeID = line[(line.index(' ') + 1):]
            return commit_changeID

    return None


def get_context(bname, sdb, udb, usha, recursive):
    """Outputs dependency of patches and fixes needed in chromeOS."""
    cs = sdb.cursor()
    cu = udb.cursor()

    cu.execute("select sha, description from commits where sha is '%s'" % usha)
    found = False

    for (sha, description) in cu.fetchall():
        # usha -> sha maping should be 1:1
        # If it isn't, skip duplicate entries.
        if found:
            print('Already found usha->sha mapping for %s , skipping row.' % sha)
            continue
        found = True
        cu.execute("select fsha, patchid, ignore from fixes where sha='%s'" % usha)
        # usha, however, may have multiple fixes
        printed = recursive
        for (fsha, patchid, ignore) in cu.fetchall():
            if ignore:
                continue
            # Check if the fix (fsha) is in our code base or
            #  try to find it using its patch ID.
            cs.execute("select sha, usha from commits \
                    where usha is '%s' or patchid is '%s'" % (fsha, patchid))
            fix = cs.fetchone()
            if not fix:
                status = get_status(fsha)
                if status != 0:
                    if not printed:
                        downstream_sha = usha_to_downstream_sha(sdb, usha)
                        print("\n[downstream_sha %s] [usha %s] ('%s')"
                                % (downstream_sha, usha, description))
                        printed = True
                    space_str = '    ' if recursive else '  '
                    print('%sCommit (upstream) %s fixed by commit (upstream) %s' %
                            (space_str, usha, fsha))
                    if status == 1:
                        print('  %sFix is missing from %s and applies cleanly'
                                    % (space_str, bname))
                    else:
                        print('  %sFix may be missing from %s; '
                                'trying to apply it results in conflicts/errors' %
                                    (space_str, bname))
                    get_context(bname, sdb, udb, fsha, True)


def missing(version, release):
    """Look for missing Fixup commits in provided chromeos or stable release."""

    bname = stable_branch(version) if release == Path.stable \
                    else chromeos_branch(version)

    print('Checking branch %s' % bname)

    subprocess.check_output(['git', 'checkout', bname], stderr=subprocess.DEVNULL)

    chosen_db = stabledb(version) if release == Path.stable \
                            else chromeosdb(version)

    sdb = sqlite3.connect(chosen_db)
    cs = sdb.cursor()
    udb = sqlite3.connect(UPSTREAMDB)

    cs.execute("select usha from commits where usha != ''")
    for usha in cs.fetchall():
        get_context(bname, sdb, udb, usha[0], False)

    udb.close()
    sdb.close()


def findmissing_helper(release):
    """Helper to find missing patches in the stable and chromeos releases."""
    if len(sys.argv) > 1:
        branches = sys.argv[1:]
    else:
        branches = config.STABLE_BRANCHES if release == Path.stable \
                else config.CHROMEOS_BRANCHES

    path = config.STABLE_PATH if release == Path.stable \
            else config.CHROMEOS_PATH
    os.chdir(path)

    for b in branches:
        missing(b, release)


def findmissing():
    """Finds missing patches in stable and chromeos releases."""
    cur_wd = os.getcwd()

    print('--Missing patches from baseline -> stable.--')
    findmissing_helper(Path.stable)

    os.chdir(cur_wd)

    print('--Missing patches from baseline -> chromeos.--')
    findmissing_helper(Path.chromeos)


if __name__ == '__main__':
    findmissing()
