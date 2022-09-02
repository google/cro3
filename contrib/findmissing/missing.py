#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Find missing stable and backported mainline fix patches in chromeos.

   isort:skip_file
"""

import logging
import os
import subprocess
import sys

import MySQLdb # pylint: disable=import-error
import requests # pylint: disable=import-error

import cloudsql_interface
import common
import gerrit_interface
import git_interface


# Constant representing number CL's we want created on single new missing patch run
NEW_CL_DAILY_LIMIT_PER_STABLE_BRANCH = 2
NEW_CL_DAILY_LIMIT_PER_BRANCH = 2


def get_subsequent_fixes(db, upstream_sha):
    """Finds all fixes that might be needed to fix the incoming commit"""
    q = """
    WITH RECURSIVE sha_graph (sha, ord) AS (
      SELECT %s as sha, 1 as ord
      UNION DISTINCT
      SELECT fixedby_upstream_sha, ord + 1
      FROM sha_graph
      JOIN upstream_fixes
      ON upstream_sha = sha
    )
    SELECT sha
    FROM sha_graph
    GROUP BY sha
    ORDER BY MAX(ord);
    """

    with db.cursor() as c:
        c.execute(q, [upstream_sha])
        return list(sum(c.fetchall(), ()))


def upstream_sha_to_kernel_sha(db, chosen_table, branch, upstream_sha):
    """Retrieves chromeos/stable sha by indexing db.

    Returns sha or None if upstream sha doesn't exist downstream.
    """
    q = f"""SELECT sha
            FROM {chosen_table}
            WHERE branch = %s
            AND (upstream_sha = %s
                OR patch_id IN (
                    SELECT patch_id
                    FROM linux_upstream
                    WHERE sha = %s
                ))"""

    with db.cursor() as c:
        c.execute(q, [branch, upstream_sha, upstream_sha])
        row = c.fetchone()

        return row[0] if row else None


def get_change_id(db, target_branch, sha):
    """Get Change-Id associated with provided upstream SHA.

    Returns Gerrit Change-Id for a provided SHA if available in either
    the chrome_fixes or the stable_fixes table as well as in Gerrit.
    None otherwise.

    If multiple Change IDs are available, pick one that has not been abandoned.
    """
    logging.info('Looking up Change ID for upstream SHA %s', sha)

    q = """SELECT c.fix_change_id, c.branch, s.fix_change_id, s.branch
        FROM linux_upstream AS l1
        JOIN linux_upstream AS l2
        ON l1.patch_id = l2.patch_id
        LEFT JOIN chrome_fixes AS c
        ON c.fixedby_upstream_sha = l2.sha
        LEFT JOIN stable_fixes as s
        ON s.fixedby_upstream_sha = l2.sha
        WHERE l1.sha = %s"""

    with db.cursor() as c:
        c.execute(q, [sha])
        rows = c.fetchall()

    change_id_cand, status_cand = None, None
    reject_list = []

    for chrome_change_id, chrome_branch, stable_change_id, stable_branch in rows:
        logging.info('Database: %s %s %s %s',
                     chrome_change_id, chrome_branch, stable_change_id, stable_branch)
        # Some entries in fixes_table do not have a change id attached.
        # This will be seen if a patch was identified as already merged
        # or as duplicate.  Skip those. Also skip empty entries returned
        # by the query above.
        # Return Change-Ids associated with abandoned CLs only if no other
        # Change-Ids are found.
        todo_list = []
        if chrome_change_id and chrome_branch:
            todo_list.append((chrome_change_id, chrome_branch))
        if stable_change_id and stable_branch:
            todo_list.append((stable_change_id, stable_branch))

        for change_id, branch in todo_list:
            try:
                # Change-IDs stored in in chrome_fixes are not always available
                # in Gerrit. This can happen, for example, if a commit was
                # created using a git instance with pre-commit hook, and the
                # commit was uploaded into Gerrit using a merge. We can not use
                # such Change-Ids. To verify, try to get the status from Gerrit
                # and skip if the Change-Id is not found.
                gerrit_status = gerrit_interface.get_status(change_id, branch)
                logging.info('Found Change ID %s in branch %s, status %s',
                             change_id, branch, gerrit_status)
                # We can not use a Change-ID which exists in Gerrit but is marked
                # as abandoned for the target branch.
                if change_id in reject_list:
                    continue
                if (branch == target_branch and
                        gerrit_status == gerrit_interface.GerritStatus.ABANDONED):
                    reject_list.append(change_id)
                    continue

                if not change_id_cand or gerrit_status != gerrit_interface.GerritStatus.ABANDONED:
                    change_id_cand, status_cand = change_id, gerrit_status
                if status_cand != gerrit_interface.GerritStatus.ABANDONED:
                    break
            except requests.exceptions.HTTPError:
                # Change-Id was not found in Gerrit
                pass

        if change_id_cand in reject_list:
            change_id_cand, status_cand = None, None

    reject = status_cand == gerrit_interface.GerritStatus.ABANDONED and bool(reject_list)
    logging.info('Returning Change-Id %s, reject=%s', change_id_cand, reject)
    return change_id_cand, reject


def find_duplicate(db, branch, upstream_sha):
    """Find and report dupplicate entry in chrome_fixes table.

    Return [kernel_sha, fixedby_upstream_sha, status] if patch is already
    in chrome_fixes table using a different upstream SHA with same patch_id,
    None otherwise.
    """
    # Check if the commit is already in the fixes table using a different SHA
    # (the same commit may be listed upstream under multiple SHAs).
    q = """SELECT c.kernel_sha, c.fixedby_upstream_sha, c.status
        FROM chrome_fixes AS c
        JOIN linux_upstream AS l1
        ON c.fixedby_upstream_sha = l1.sha
        JOIN linux_upstream AS l2
        ON l1.patch_id = l2.patch_id
        WHERE l1.sha != l2.sha
        AND c.branch = %s
        AND l2.sha = %s"""

    with db.cursor() as c:
        c.execute(q, [branch, upstream_sha])
        return c.fetchone()


def insert_by_patch_id(db, branch, fixed_sha, fixedby_upstream_sha):
    """Handles case where fixedby_upstream_sha may have changed in kernels.

    Returns True if successful patch_id insertion and False if patch_id not found.
    """
    c = db.cursor()

    duplicate = find_duplicate(db, branch, fixedby_upstream_sha)
    if duplicate:
        # This commit is already queued or known under a different upstream SHA.
        # Mark it as abandoned and point to the other entry as reason.
        kernel_sha, recorded_upstream_sha, status = duplicate
        # kernel_sha is the SHA in the database.
        # fixed_sha is the SHA we are trying to fix, which matches kernel_sha
        # (meaning both have the same patch ID).
        # The entry we need to add to the fixes table is for fixed_sha, not for
        # kernel_sha (because kernel_sha is already in the database).
        reason = 'Already merged/queued into linux_chrome [upstream sha %s]' % recorded_upstream_sha
        logging.info('SHA %s [%s] fixed by %s: %s',
                     fixed_sha, kernel_sha, fixedby_upstream_sha, reason)

        try:
            q = """INSERT INTO chrome_fixes
                        (kernel_sha, fixedby_upstream_sha, branch, entry_time,
                        close_time, initial_status, status, reason)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
            # Status must be OPEN, MERGED or ABANDONED since we don't have
            # entries with CONFLICT in the fixes table.
            # Change OPEN to ABANDONED for final status, but keep MERGED.
            final_status = status
            if final_status == common.Status.OPEN.name:
                final_status = common.Status.ABANDONED.name
            # ABANDONED is not a valid initial status. Change it to OPEN
            # if encountered.
            if status == common.Status.ABANDONED.name:
                status = common.Status.OPEN.name
            entry_time = common.get_current_time()
            c.execute(q, [fixed_sha, fixedby_upstream_sha,
                              branch, entry_time, entry_time,
                              status, final_status, reason])
            db.commit()
        except MySQLdb.Error as e: # pylint: disable=no-member
            logging.error(
                'Failed to insert an already merged/queued entry into chrome_fixes: error %d (%s)',
                e.args[0], e.args[1])
        return True

    # Commit sha may have been modified in cherry-pick, backport, etc.
    # Retrieve SHA in linux_chrome by patch-id by checking for fixedby_upstream_sha
    #  removes entries that are already tracked in chrome_fixes
    q = """SELECT lc.sha
            FROM linux_chrome AS lc
            JOIN linux_upstream AS lu
            ON lc.patch_id = lu.patch_id
            JOIN upstream_fixes as uf
            ON lc.upstream_sha = uf.upstream_sha
            WHERE uf.fixedby_upstream_sha = %s AND branch = %s
            AND (lc.sha, uf.fixedby_upstream_sha)
            NOT IN (
                SELECT kernel_sha, fixedby_upstream_sha
                FROM chrome_fixes
                WHERE branch = %s
            )"""
    c.execute(q, [fixedby_upstream_sha, branch, branch])
    chrome_shas = c.fetchall()

    # fixedby_upstream_sha has already been merged into linux_chrome
    #  chrome shas represent kernel sha for the upstream_sha fixedby_upstream_sha
    if chrome_shas:
        for chrome_sha in chrome_shas:
            entry_time = common.get_current_time()
            cl_status = common.Status.MERGED.name
            reason = 'Already merged into linux_chrome [upstream sha %s]' % fixedby_upstream_sha

            try:
                q = """INSERT INTO chrome_fixes
                        (kernel_sha, fixedby_upstream_sha, branch, entry_time,
                        close_time, initial_status, status, reason)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
                c.execute(q, [chrome_sha, fixedby_upstream_sha, branch, entry_time,
                                entry_time, cl_status, cl_status, reason])
                db.commit()
            except MySQLdb.Error as e: # pylint: disable=no-member
                logging.error(
                    'Failed to insert an already merged entry into chrome_fixes: error %d(%s)',
                    e.args[0], e.args[1])
        return True

    return False


def insert_fix_gerrit(db, chosen_table, chosen_fixes, branch, kernel_sha, fixedby_upstream_sha,
                      recursion=False):
    """Inserts fix row by checking status of applying a fix change.

    Return True if we create a new Gerrit CL, otherwise return False.
    """
    # Check if fix has been merged using it's patch-id since sha's might've changed
    success = insert_by_patch_id(db, branch, kernel_sha, fixedby_upstream_sha)
    created_new_change = False
    if success:
        return created_new_change

    handler = git_interface.commitHandler(common.Kernel.linux_chrome, branch=branch,
                                          full_reset=not recursion)
    # Try applying patch and get status
    status = handler.cherrypick_status(fixedby_upstream_sha)
    initial_status = status.name
    current_status = status.name

    entry_time = common.get_current_time()

    close_time = fix_change_id = reason = None

    q = f"""INSERT INTO {chosen_fixes}
            (kernel_sha, fixedby_upstream_sha, branch, entry_time, close_time,
            fix_change_id, initial_status, status, reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""

    if status == common.Status.MERGED:
        # Create a row for the merged CL (we don't need to track this), but can be stored
        # to indicate that the changes of this patch are already merged
        # entry_time and close_time are the same since we weren't tracking when it was merged
        fixedby_kernel_sha = upstream_sha_to_kernel_sha(db, chosen_table,
                branch, fixedby_upstream_sha)
        logging.info('%s SHA [%s] already merged bugfix patch [kernel: %s] [upstream: %s]',
                     chosen_fixes, kernel_sha, fixedby_kernel_sha, fixedby_upstream_sha)

        reason = 'Patch applied to linux_chrome before this robot was run'
        close_time = entry_time

        # linux_chrome will have change-id's but stable merged fixes will not
        # Correctly located fixedby_kernel_sha in linux_chrome
        if chosen_table == 'linux_chrome' and fixedby_kernel_sha:
            fix_change_id = git_interface.get_commit_changeid_linux_chrome(fixedby_kernel_sha)
    elif status == common.Status.OPEN:
        change_id, rejected = get_change_id(db, branch, fixedby_upstream_sha)
        if rejected:
            # A change-Id for this commit exists in the target branch, but it is marked
            # as ABANDONED and we can not use it. Create a database entry and mark the commit
            # as abandoned to prevent it from being retried over and over again.
            current_status = common.Status.ABANDONED.name
        else:
            fix_change_id = gerrit_interface.create_change(kernel_sha, fixedby_upstream_sha, branch,
                                                           chosen_table == 'linux_chrome',
                                                           change_id)
            created_new_change = bool(fix_change_id)

            # Checks if change was created successfully
            if not created_new_change:
                logging.error('Failed to create change for kernel_sha %s fixed by %s',
                              kernel_sha, fixedby_upstream_sha)
                return False
    elif status == common.Status.CONFLICT:
        # Register conflict entry_time, do not create gerrit CL
        # Requires engineer to manually explore why CL doesn't apply cleanly
        pass

    try:
        with db.cursor() as c:
            c.execute(q, [kernel_sha, fixedby_upstream_sha, branch, entry_time,
                          close_time, fix_change_id, initial_status, current_status, reason])
        logging.info('Inserted row into fixes table %s %s %s %s %s %s %s %s %s %s',
                     chosen_fixes, kernel_sha, fixedby_upstream_sha, branch,
                     entry_time, close_time, fix_change_id, initial_status, current_status, reason)

    except MySQLdb.Error as e: # pylint: disable=no-member
        logging.error(
            'Error inserting fix CL into fixes table %s %s %s %s %s %s %s %s %s %s: error %d(%s)',
            chosen_fixes, kernel_sha, fixedby_upstream_sha, branch,
            entry_time, close_time, fix_change_id, initial_status, current_status, reason,
            e.args[0], e.args[1])

    if created_new_change and not recursion:
        subsequent_fixes = get_subsequent_fixes(db, fixedby_upstream_sha)
        if subsequent_fixes:
            subsequent_fixes.pop(0) # 1st returned SHA is fixedby_upstream_sha
            for fix in subsequent_fixes:
                logging.info('SHA %s recursively fixed by: %s', fixedby_upstream_sha, fix)
                insert_fix_gerrit(db, chosen_table, chosen_fixes, branch, kernel_sha, fix, True)

    return created_new_change


def fixup_unmerged_patches(db, branch, kernel_metadata):
    """Fixup script that attempts to reapply unmerged fixes to get latest status.

    2 main actions performed by script include:
        1) Handle case where a conflicting CL later can be applied cleanly without merge conflicts
        2) Detect if the fix has been applied to linux_chrome externally
            (i.e not merging through a fix created by this robot)
    """
    fixes_table = kernel_metadata.kernel_fixes_table
    q = f"""SELECT kernel_sha, fixedby_upstream_sha, status, fix_change_id
            FROM {fixes_table}
            WHERE status != 'MERGED'
            AND branch = %s"""
    handler = git_interface.commitHandler(common.Kernel.linux_chrome, branch)

    with db.cursor() as c:
        c.execute(q, [branch])
        rows = c.fetchall()

    for kernel_sha, fixedby_upstream_sha, status, fix_change_id in rows:
        new_status_enum = handler.cherrypick_status(fixedby_upstream_sha,
                                                    apply=status != 'ABANDONED')
        if not new_status_enum:
            continue

        new_status = new_status_enum.name

        if status == 'CONFLICT' and new_status == 'OPEN':
            change_id, rejected = get_change_id(db, branch, fixedby_upstream_sha)
            if rejected:
                # The cherry-pick was successful, but the commit is marked as abandoned
                # in gerrit. Mark it accordingly.
                reason = 'Fix abandoned in Gerrit'
                cloudsql_interface.update_change_abandoned(db, fixes_table, kernel_sha,
                                                           fixedby_upstream_sha, reason)
            else:
                fix_change_id = gerrit_interface.create_change(kernel_sha, fixedby_upstream_sha,
                                        branch, kernel_metadata.path == 'linux_chrome', change_id)

                # Check if we successfully created the fix patch before performing update
                if fix_change_id:
                    cloudsql_interface.update_conflict_to_open(db, fixes_table,
                                        kernel_sha, fixedby_upstream_sha, fix_change_id)
        elif new_status == 'MERGED':
            # This specifically includes situations where a patch marked ABANDONED
            # in the database was merged at some point anyway.
            reason = 'Fix was merged externally and detected by robot.'
            if fix_change_id:
                gerrit_interface.abandon_change(fix_change_id, branch, reason)
            cloudsql_interface.update_change_merged(db, fixes_table,
                                        kernel_sha, fixedby_upstream_sha, reason)


def update_fixes_in_branch(db, branch, kernel_metadata, limit):
    """Updates fix patch table row by determining if CL merged into linux_chrome."""
    del limit # unused here

    chosen_fixes = kernel_metadata.kernel_fixes_table

    # Old rows to Update
    q = f"""UPDATE {chosen_fixes} AS fixes
           JOIN linux_chrome AS lc
           ON fixes.fixedby_upstream_sha = lc.upstream_sha
           SET status = 'MERGED', close_time = %s, reason = %s
           WHERE fixes.branch = %s
           AND lc.branch = %s
           AND (fixes.status = 'OPEN'
                OR fixes.status = 'CONFLICT'
                OR fixes.status = 'ABANDONED')"""

    close_time = common.get_current_time()
    reason = 'Patch has been applied to linux_chome'

    try:
        with db.cursor() as c:
            c.execute(q, [close_time, reason, branch, branch])
        logging.info(
            'Updating rows that have been merged into linux_chrome in table %s / branch %s',
            chosen_fixes, branch)
    except MySQLdb.Error as e: # pylint: disable=no-member
        logging.error('Error updating fixes table for merged commits %s %s %s %s: %d(%s)',
                      chosen_fixes, close_time, reason, branch, e.args[0], e.args[1])
    db.commit()

    # Sync status of unmerged patches in a branch
    fixup_unmerged_patches(db, branch, kernel_metadata)


def create_new_fixes_in_branch(db, branch, kernel_metadata, limit):
    """Look for missing Fixup commits in provided chromeos or stable release."""
    branch_name = kernel_metadata.get_kernel_branch(branch)

    logging.info('Checking branch %s', branch_name)
    subprocess.run(['git', 'checkout', branch_name], check=True,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # chosen_table is either linux_stable or linux_chrome
    chosen_table = kernel_metadata.path
    chosen_fixes = kernel_metadata.kernel_fixes_table

    # New rows to insert
    # Note: MySQLdb doesn't support inserting table names as parameters
    #   due to sql injection
    q = f"""SELECT chosen_table.sha, uf.fixedby_upstream_sha
            FROM {chosen_table} AS chosen_table
            JOIN upstream_fixes AS uf
            ON chosen_table.upstream_sha = uf.upstream_sha
            WHERE branch = %s
            AND (chosen_table.sha, uf.fixedby_upstream_sha)
            NOT IN (
                SELECT chosen_fixes.kernel_sha, chosen_fixes.fixedby_upstream_sha
                FROM {chosen_fixes} AS chosen_fixes
                WHERE branch = %s
            )"""

    try:
        with db.cursor() as c:
            c.execute(q, [branch, branch])
            rows = c.fetchall()

        logging.info('Finding new rows to insert into fixes table %s %s %s',
                     chosen_table, chosen_fixes, branch)
    except MySQLdb.Error as e: # pylint: disable=no-member
        logging.error('Error finding new rows to insert %s %s %s: error %d(%s)',
                      chosen_table, chosen_fixes, branch, e.args[0], e.args[1])

    count_new_changes = 0
    # todo(hirthanan): Create an intermediate state in Status that allows us to
    #   create all the patches in chrome/stable fixes tables but does not add reviewers
    #   until quota is available. This should decouple the creation of gerrit CL's
    #   and adding reviewers to those CL's.
    for kernel_sha, fixedby_upstream_sha in rows:
        new_change = insert_fix_gerrit(db, chosen_table, chosen_fixes,
                                        branch, kernel_sha, fixedby_upstream_sha)
        if new_change:
            count_new_changes += 1
        if count_new_changes >= limit:
            break

    db.commit()
    return count_new_changes


def missing_patches_sync(db, kernel_metadata, sync_branch_method, limit=None):
    """Helper to create or update fix patches in stable and chromeos releases."""
    if len(sys.argv) > 1:
        branches = sys.argv[1:]
    else:
        branches = common.CHROMEOS_BRANCHES

    os.chdir(common.get_kernel_absolute_path(kernel_metadata.path))

    for b in branches:
        sync_branch_method(db, b, kernel_metadata, limit)

    os.chdir(common.WORKDIR)


def new_missing_patches():
    """Rate limit calling create_new_fixes_in_branch."""
    with common.connect_db() as db:
        kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_stable)
        missing_patches_sync(db, kernel_metadata, create_new_fixes_in_branch,
                             NEW_CL_DAILY_LIMIT_PER_STABLE_BRANCH)

        kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_chrome)
        missing_patches_sync(db, kernel_metadata, create_new_fixes_in_branch,
                             NEW_CL_DAILY_LIMIT_PER_BRANCH)


def update_missing_patches():
    """Updates fixes table entries on regular basis."""
    with common.connect_db() as db:
        kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_stable)
        missing_patches_sync(db, kernel_metadata, update_fixes_in_branch)

        kernel_metadata = common.get_kernel_metadata(common.Kernel.linux_chrome)
        missing_patches_sync(db, kernel_metadata, update_fixes_in_branch)
