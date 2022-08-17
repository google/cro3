#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module parses and stores mainline linux patches to be easily accessible.

   isort:skip_file
"""

import contextlib
import logging
import re
import subprocess

import MySQLdb.constants.ER # pylint: disable=import-error
import MySQLdb # pylint: disable=import-error

import common
import util


RF = re.compile(r'^\s*Fixes: (?:commit )*([0-9a-f]+).*')
RDESC = re.compile(r'.* \("([^"]+)"\).*')
REVERT = re.compile(r'^\s*This reverts commit ([0-9a-f]+).*')


class Fix():
    """Structure to store upstream_fixes object.

    TODO(hirthanan) write method to produce insert query for better encapsulation
    """
    upstream_sha = fixedby_upstream_sha = None

    def __init__(self, _upstream_sha, _fixedby_upstream_sha):
        self.upstream_sha = _upstream_sha
        self.fixedby_upstream_sha = _fixedby_upstream_sha


def update_upstream_table(branch, start, db):
    """Updates the linux upstream commits and linux upstream fixes tables.

    Also keep a reference of last parsed SHA so we don't have to index the
        entire commit log on each run.
    """
    logging.info('Linux upstream on branch %s', branch)
    cursor = db.cursor()

    logging.info('Pulling all the latest linux-upstream commits')
    subprocess.check_output(['git', 'pull'])

    logging.info('Loading all linux-upstream commit logs from %s', start)
    cmd = ['git', 'log', '--abbrev=12', '--oneline', '--reverse', start + '..HEAD']
    commits = subprocess.check_output(cmd, encoding='utf-8', errors='ignore')

    fixes = []
    last = None
    logging.info('Analyzing upstream commits to build linux_upstream and fixes tables.')

    for commit in commits.splitlines():
        if commit != '':
            elem = commit.split(' ', 1)
            sha = elem[0]
            last = sha

            # Nothing else to do if the commit is a merge
            if util.is_merge_commit(sha):
                continue

            description = elem[1].rstrip('\n')

            # Calculate patch ID
            patch_id = util.calc_patch_id(sha)

            try:
                q = """INSERT INTO linux_upstream
                        (sha, description, patch_id)
                        VALUES (%s, %s, %s)"""
                cursor.execute(q, [sha, description, patch_id])
                logging.info('Inserted sha %s into linux_upstream', sha)
            except MySQLdb.Error as e: # pylint: disable=no-member
                # Don't complain about duplicate entries; those are seen all the time
                # due to git idiosyncrasies (non-linearity).
                if e.args[0] != MySQLdb.constants.ER.DUP_ENTRY:
                    logging.error(
                        'Issue inserting sha "%s", description "%s", patch_id "%s": error %d (%s)',
                        sha, description, patch_id, e.args[0], e.args[1])
                continue
            except UnicodeEncodeError as e:
                logging.error('Failed to INSERT upstream sha %s with description %s: error %s',
                        sha, description, e)
                continue

            # check if this patch fixes a previous patch.
            subprocess_cmd = ['git', 'show', '-s', '--pretty=format:%b', sha]
            description = subprocess.check_output(subprocess_cmd,
                                                    encoding='utf-8', errors='ignore')
            for d in description.splitlines():
                m = RF.search(d)
                fsha = None
                if m and m.group(1):
                    try:
                        # Normalize fsha to 12 characters
                        cmd = 'git show -s --abbrev=12 --pretty=format:%h ' + m.group(1)
                        fsha = subprocess.check_output(cmd.split(' '),
                                stderr=subprocess.DEVNULL, encoding='utf-8', errors='ignore')
                    except subprocess.CalledProcessError:
                        logging.error('SHA %s fixes commit %s: Not found', sha, m.group(0))
                        m = RDESC.search(d)
                        if m:
                            desc = m.group(1)
                            desc = desc.replace("'", "''")
                            q = """SELECT sha
                                    FROM linux_upstream
                                    WHERE description = %s"""
                            cursor.execute(q, [desc])
                            fsha = cursor.fetchone()
                            if fsha:
                                fsha = fsha[0]
                                logging.info('  Description matches with SHA %s', fsha)
                        # The Fixes: tag may be wrong. The sha may not be in the
                        # upstream kernel, or the format may be completely wrong
                        # and m.group(1) may not be a sha in the first place.
                        # In that case, do nothing.
                if fsha:
                    logging.info('Commit %s fixed by %s', fsha[0:12], sha)

                    # Add fixes to list to be added after linux_upstream
                    #  table is fully contructed to avoid Foreign key errors in SQL
                    fix_obj = Fix(_upstream_sha=fsha[0:12], _fixedby_upstream_sha=sha)
                    fixes.append(fix_obj)

                m = REVERT.search(d)
                rsha = None
                if m and m.group(1):
                    try:
                        # Normalize rsha to 12 characters
                        cmd = 'git show -s --abbrev=12 --pretty=format:%h ' + m.group(1)
                        rsha = subprocess.check_output(cmd.split(' '),
                                stderr=subprocess.DEVNULL, encoding='utf-8', errors='ignore')
                    except subprocess.CalledProcessError:
                        pass
                if rsha:
                    # Deduplicate if it has set Fixes tag.
                    if fsha is None or fsha[0:12] != rsha[0:12]:
                        logging.info('Commit %s reverted by %s', rsha[0:12], sha)

                        # Add fixes to list to be added after linux_upstream
                        #  table is fully contructed to avoid Foreign key errors in SQL
                        fix_obj = Fix(_upstream_sha=rsha[0:12], _fixedby_upstream_sha=sha)
                        fixes.append(fix_obj)

    for fix in fixes:
        # Update sha, fsha pairs
        q = """INSERT INTO upstream_fixes (upstream_sha, fixedby_upstream_sha)
                VALUES (%s, %s)"""
        try:
            cursor.execute(q, [fix.upstream_sha, fix.fixedby_upstream_sha])
        except MySQLdb.IntegrityError as e: # pylint: disable=no-member
            # TODO(hirthanan): Email mailing list that one of usha or fix_usha is missing
            logging.error('CANNOT FIND commit %s fixed by %s: error %d (%s)',
                    fix.upstream_sha, fix.fixedby_upstream_sha, e.args[0], e.args[1])

    # Update previous fetch database
    if last:
        common.update_previous_fetch(db, common.Kernel.linux_upstream, branch, last)

    db.commit()


if __name__ == '__main__':
    with contextlib.closing(common.connect_db()) as cloudsql_db:
        kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_upstream)
        common.update_kernel_db(cloudsql_db, kernel_metadata)
