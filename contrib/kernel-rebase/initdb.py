#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Initialize rebase database"""

import sqlite3
import os
import re
import subprocess
import time
from common import rebasedb
from common import stable_path, android_path, chromeos_path
from common import stable_baseline, rebase_baseline, rebase_target_tag

stable_commits = rebase_baseline() + '..' + stable_baseline()
baseline_commits = rebase_baseline() + '..'

# "commit" is sometimes seen multiple times, such as with commit 6093aabdd0ee
cherrypick = re.compile(r'cherry picked from (commit )+([a-z0-9]+)')
stable = re.compile(r'(commit )+([a-z0-9]+) upstream')
stable2 = re.compile(r'Upstream (commit )+([a-z0-9]+)')
upstream = re.compile(r'(ANDROID: *|UPSTREAM: *|FROMGIT: *|BACKPORT: *)+(.*)')
chromium = re.compile(r'(CHROMIUM: *|FROMLIST: *)+(.*)')
changeid = re.compile(r'\s*Change-Id:\s+(I[a-z0-9]+)')


def NOW():
    """Return current time"""

    return int(time.time())


def removedb():
    """remove database if it exists"""

    try:
        os.remove(rebasedb)
    except OSError:
        pass


def createdb():
    """remove and recreate database"""

    removedb()

    conn = sqlite3.connect(rebasedb)
    c = conn.cursor()

    # Create table
    c.execute('CREATE TABLE commits (date integer, \
                                   created timestamp, updated timestamp, \
                                   authored timestamp, committed timestamp, \
                                   sha text, usha text, \
                                   patchid text, \
                                   changeid text, \
                                   subject text, topic integer, \
                                   contact text, \
                                   email text, \
                                   disposition text, reason text, \
                                   sscore integer, pscore integer, dsha text)')
    c.execute('CREATE UNIQUE INDEX commit_date ON commits (date)')
    c.execute('CREATE INDEX commit_sha ON commits (sha)')
    c.execute('CREATE INDEX upstream_sha ON commits (usha)')
    c.execute('CREATE INDEX patch_id ON commits (patchid)')

    c.execute('CREATE TABLE files (sha text, filename text)')
    c.execute('CREATE INDEX file_sha ON files (sha)')
    c.execute('CREATE INDEX file_name ON files (filename)')

    c.execute('CREATE TABLE stable (sha, origin)')
    c.execute('CREATE UNIQUE INDEX stable_sha ON stable (sha)')

    c.execute('CREATE TABLE topics (topic integer, name text)')
    c.execute('CREATE UNIQUE INDEX topics_index ON topics (topic)')

    # Save (commit) the changes
    conn.commit()
    conn.close()


# date:
#         git show --format="%ct" -s ${sha}
# subject:
#        git show --format="%s" -s ${sha}
# file list:
#        git show --name-only --format="" ${sha}

# Insert a row of data
# c.execute("INSERT INTO commits VALUES (1489758183,sha,subject)")
# c.execute("INSERT INTO files VALUES (sha,filename)")
# sha and filename must be in ' '


def update_stable(path, sha_list, origin):
    """Create list of SHAs from provided path and commit list.

    Skip if entry (sha) is already in database.
    """

    conn = sqlite3.connect(rebasedb)
    c = conn.cursor()

    cmd = ['git', '-C', path, 'log', '--no-merges', '--abbrev=12', '--oneline',
           '--reverse', sha_list]
    commits = subprocess.check_output(cmd, encoding='utf-8', errors='ignore')

    for commit in commits.splitlines():
        if commit != '':
            elem = commit.split(' ')[:1]
            sha = elem[0]
            c.execute("select sha from stable where sha is '%s'" % sha)
            found = c.fetchall()
            if found == []:
                c.execute('INSERT INTO stable(sha, origin) VALUES (?, ?)', (
                    sha,
                    origin,
                ))

    conn.commit()
    conn.close()


def get_contact(path, sha):
    """Return first commit signer, tester, or submitter with a Google e-mail address.

    If there is none, pick the last reviewer.
    If there is none, return None, None.
    """
    contact = None
    email = None

    cmd = ['git', '-C', path, 'log', '--format=%B', '-n', '1', sha]
    commit_message = subprocess.check_output(
        cmd, encoding='utf-8', errors='ignore')
    tags = 'Signed-off-by|Commit-Queue|Tested-by'
    domains = 'chromium.org|google.com|collabora.com'
    m = '^(?:%s): (.*) <(.*@(?:%s))>$' % (tags, domains)
    emails = re.findall(m, commit_message, re.M)
    if emails:
        contact, email = emails[0]
    else:
        tags = 'Reviewed-by'
        m = '^(?:%s): (.*) <(.*@(?:%s))>$' % (tags, domains)
        emails = re.findall(m, commit_message, re.M)
        if emails:
            contact, email = emails[-1]
    return contact, email


def update_commits():
    """Get complete list of commits from rebase baseline.

    Assume that the baseline branch exists and has been checked out.
    """

    conn = sqlite3.connect(rebasedb)
    c = conn.cursor()

    cmd = ['git', '-C', chromeos_path, 'log', '--no-merges', '--abbrev=12',
           '--reverse', '--format=%at%x01%ct%x01%h%x01%an%x01%ae%x01%s',
           rebase_baseline() + '..']
    commits = subprocess.check_output(cmd, encoding='utf-8', errors='ignore')

    prevdate = 0
    mprevdate = 0
    for commit in commits.splitlines(): # pylint: disable=too-many-nested-blocks
        if commit != '':
            elem = commit.split('\001', 5)
            authored = elem[0]
            committed = elem[1]
            sha = elem[2]
            contact = elem[3]
            email = elem[4]

            if ('@google.com' not in email and '@chromium.org' not in email
                    and '@collabora.com' not in email):
                ncontact, nemail = get_contact(chromeos_path, sha)
                if ncontact:
                    contact = ncontact
                    email = nemail

            subject = elem[5].rstrip('\n')

            ps = subprocess.Popen(['git', '-C', chromeos_path, 'show', sha], stdout=subprocess.PIPE)
            spid = subprocess.check_output(['git', '-C', chromeos_path, 'patch-id'],
                                           stdin=ps.stdout, encoding='utf-8', errors='ignore')
            patchid = spid.split(' ', 1)[0]

            # Make sure date is unique and in ascending order.
            date = int(committed)
            if date == prevdate:
                date = mprevdate + 1
            else:
                prevdate = date
                date = date * 1000
            mprevdate = date

            # Do nothing if the sha is already in the commit table.
            c.execute("select sha from commits where sha='%s'" % sha)
            found = c.fetchone()
            if found:
                continue

            # check for cherry pick lines. If so, record the upstream SHA associated
            # with this commit. Only look for commits which may be upstream or may
            # have been merged from a stable release.
            usha = ''
            if not chromium.match(subject):
                u = upstream.match(subject)
                desc = subprocess.check_output(['git', '-C', chromeos_path, 'show', '-s', sha],
                                               encoding='utf-8', errors='ignore')
                for d in desc.splitlines():
                    m = None
                    if u:
                        m = cherrypick.search(d)
                    else:
                        m = stable.search(d)
                        if not m:
                            m = stable2.search(d)
                    if m:
                        usha = m.group(2)[:12]
                        # The patch may have been picked multiple times; only record
                        # the first entry.
                        break

            # Search for embedded Change-Id string.
            # If found, add it to database.
            desc = subprocess.check_output(['git', '-C', chromeos_path, 'show', '-s', sha],
                                           encoding='utf-8', errors='ignore')
            for d in desc.splitlines():
                chid = changeid.match(d)
                if chid:
                    chid = chid.group(1)
                    break

            # Initially assume we'll drop everything because it is not listed when
            # running "rebase -i". Before doing that, check if the commit is a
            # stable release commit. If so, mark it accordingly.
            reason = 'upstream'
            c.execute("select sha from stable where sha is '%s'" % sha)
            if c.fetchone():
                reason = 'stable'

            q = """
                INSERT INTO commits(date, created, updated, authored, committed, contact,
                                     email, sha, usha, patchid, changeid, subject,
                                     disposition, reason)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            c.execute(q,
                (date, NOW(), NOW(), authored, committed, contact, email,
                 sha, usha, patchid, chid, subject, 'drop', reason))
            filenames = subprocess.check_output(
                ['git', '-C', chromeos_path, 'show', '--name-only', '--format=', sha],
                encoding='utf-8', errors='ignore')
            for fn in filenames.splitlines():
                if fn != '':
                    c.execute('INSERT INTO files(sha, filename) VALUES (?, ?)',
                              (
                                  sha,
                                  fn,
                              ))

    conn.commit()

    # "git cherry -v <target>" on branch rebase_baseline gives us a list
    # of patches to apply.
    patches = subprocess.check_output(
        ['git', '-C', chromeos_path, 'cherry', '-v', rebase_target_tag()],
        encoding='utf-8', errors='ignore')
    for patch in patches.splitlines():
        elem = patch.split(' ', 2)
        # print("patch: " + patch)
        # print("elem[0]: '%s' elem[1]: '%s' elem[2]: '%s'" % (elem[0], elem[1], elem[2]))
        if elem[0] == '+':
            # patch not found upstream
            sha = elem[1][:12]
            # Try to find patch in stable branch. If it is there, drop it after all.
            # If not, we may need to apply it.
            c.execute("select sha, origin from stable where sha is '%s'" % sha)
            found = c.fetchone()
            if found:
                c.execute(
                    "UPDATE commits SET disposition=('drop') where sha='%s'" %
                    sha)
                c.execute("UPDATE commits SET reason=('%s') where sha='%s'" %
                          (found[1], sha))
                c.execute("UPDATE commits SET updated=('%d') where sha='%s'" %
                          (NOW(), sha))
            else:
                # We need to check if the commit is already marked as drop
                # with a reason other than "upstream". If so, don't update it.
                c.execute(
                    "select disposition, reason from commits where sha='%s'" %
                    sha)
                found = c.fetchone()
                if found and found[0] == 'drop' and found[1] == 'upstream':
                    c.execute(
                        "UPDATE commits SET disposition=('pick') where sha='%s'"
                        % sha)
                    c.execute("UPDATE commits SET reason=('') where sha='%s'" %
                              sha)
                    c.execute(
                        "UPDATE commits SET updated=('%d') where sha='%s'" %
                        (NOW(), sha))

    conn.commit()
    conn.close()


if not os.path.isfile(rebasedb):
    createdb()

if stable_path:
    update_stable(stable_path, stable_commits, 'stable')
if android_path:
    update_stable(android_path, baseline_commits, 'android')
update_commits()
