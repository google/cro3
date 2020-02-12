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
from enum import Enum

import common
from common import stabledb, UPSTREAMDB, stable_branch, chromeosdb, \
        chromeos_branch, patch_link, patchdb_stable, patchdb_chromeos, createdb
from patch import PatchEntry, Status, make_patch_table


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


def get_context(bname, sdb, udb, pdb, usha, recursive):
    """Outputs dependency of patches and fixes needed in chromeOS."""
    cs = sdb.cursor()
    cu = udb.cursor()
    cp = pdb.cursor()

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
                    patch = PatchEntry(None, usha, fsha, None, None, None)
                    if not printed:
                        downstream_sha = usha_to_downstream_sha(sdb, usha)
                        print("\n[downstream_sha %s] [usha %s] ('%s')"
                                % (downstream_sha, usha, description))
                        printed = True

                        # Retrieve downstream changeid (stable will return None)
                        cs.execute("select changeid from commits \
                                    where sha is '%s'" % downstream_sha)
                        downstream_changeid = cs.fetchone()
                        downstream_link = patch_link(downstream_changeid)

                        patch.set_downstream_sha(downstream_sha)

                        # Set the downstream link if dealing with chromeos branches
                        #  since chromeos commits should have associated changeid
                        is_chromeos_branch = bname.startswith('chromeos')

                        # pylint: disable=expression-not-assigned
                        patch.set_downstream_link(downstream_link) if is_chromeos_branch else None

                    space_str = '    ' if recursive else '  '
                    print('%sCommit (upstream) %s fixed by commit (upstream) %s' %
                            (space_str, usha, fsha))
                    if status == 1:
                        print('  %sFix is missing from %s and applies cleanly'
                                    % (space_str, bname))
                        # Create gerrit change ticket here
                        #  if succesfully created set status to OPEN
                        fix_changeid = 0
                        fix_link = patch_link(fix_changeid)

                        patch.set_fix_link(fix_link)
                        patch.set_status(Status.NEW)
                    else:
                        print('  %sFix may be missing from %s; '
                                'trying to apply it results in conflicts/errors' %
                                    (space_str, bname))

                        patch.set_status(Status.CONF)

                    cp.execute('INSERT INTO patches(downstream_sha, usha,' \
                            'fix_usha, downstream_link, fix_link, status)' \
                            ' VALUES (?, ?, ?, ?, ?, ?)',
                            (patch.downstream_sha, patch.usha,
                                patch.fsha, patch.downstream_link,
                                patch.fix_link, patch.status.name))
                    get_context(bname, sdb, udb, pdb, fsha, True)


def missing(version, release):
    """Look for missing Fixup commits in provided chromeos or stable release."""

    bname = stable_branch(version) if release == Path.stable \
                    else chromeos_branch(version)

    print('Checking branch %s' % bname)

    subprocess.check_output(['git', 'checkout', bname], stderr=subprocess.DEVNULL)

    chosen_db = stabledb(version) if release == Path.stable \
            else chromeosdb(version)

    patch_db = patchdb_stable(version) if release == Path.stable \
            else patchdb_chromeos(version)

    # resets patch table data since data may have changed
    createdb(patch_db, make_patch_table)

    sdb = sqlite3.connect(chosen_db)
    pdb = sqlite3.connect(patch_db)
    cs = sdb.cursor()
    udb = sqlite3.connect(UPSTREAMDB)

    cs.execute("select usha from commits where usha != ''")
    for usha in cs.fetchall():
        get_context(bname, sdb, udb, pdb, usha[0], False)

    pdb.commit()
    pdb.close()

    udb.close()
    sdb.close()


def findmissing_helper(release):
    """Helper to find missing patches in the stable and chromeos releases."""
    if len(sys.argv) > 1:
        branches = sys.argv[1:]
    else:
        branches = common.SUPPORTED_KERNELS

    path = common.STABLE_PATH if release == Path.stable \
            else common.CHROMEOS_PATH
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
