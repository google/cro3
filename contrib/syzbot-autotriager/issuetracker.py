# -*- coding: utf-8 -*-
# Copyright 2018 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for working with chromeos sysbot bugs on issuetracker."""

from __future__ import print_function

import base64
import pickle
import subprocess

import config
import simpledb
import utils


def clean_st(st):
    """Cleans the stacktraces obtained from Issuetracker.

    Parses and cleans the stacktraces obtained from an Issuetracker
    bug. It returns a list of sets, with each string in the set being
    a function name in the stacktrace.

    Args:
        st: A list of sets, with each set representing a stacktrace.

    Returns:
        A list of sets, each of which contain cleaned function names.
        An example below.
        [set(['kthread', 'worker_thread', 'ret_from_fork'])]
    """
    ret = []
    for stacktrace in st:
        temp = set()
        for fnname in stacktrace:
            fnname = fnname.strip()
            if fnname.startswith('<'):
                index = 3 if '?' in fnname else 2
            elif fnname.startswith('['):
                index = 1
            else:
                index = 0

            try:
                fnname = fnname.split()[index]
            except IndexError as _:
                print('[x] Error parsing %s' % (repr(fnname)))
                fnname = ''

            if not fnname:
                continue

            fnname = fnname.split('+')[0]
            if not fnname:
                continue

            temp.add(fnname)
        ret.append(temp)
    return ret


def get_stacktrace(lineno, lines):
    """Obtain the stacktrace from the an IssueTracker bug.

    Given the content of an issuetracker bug, obtain all stacktraces,
    clean, and return. This returns a list of set of strings, with
    each string representing a function in the stacktrace.

    Args:
        lineno: This tells where to start processing lines from.
        lines: A list of strings containing bug details.

    Returns:
        A list of sets, each set corresponding to one stacktrace.
        (One issuetracker bug might contain multiple stacktraces).
        An example below.
        [set(['kthread', 'worker_thread', 'ret_from_fork'])]
    """
    remove_marker = lambda x: x[2:] if x.startswith('> ') else x
    st, d = list(), set()
    inside_st = False
    for line in lines[lineno:]:
        line = remove_marker(line)
        if line == IssuetrackerBug.ST_START_MARKER:
            if d:
                st.append(d)
                d = set()
            inside_st = True
        elif inside_st and line.startswith(' '):
            d.add(line)
        else:
            inside_st = False
    if d:
        st.append(d)

    st = clean_st(st)
    return st


class IssuetrackerBug(object):
    """IssuetrackerBug represents one parsed issuetracker bug."""
    COMMIT_MARKER = 'syzbot hit the following crash on '
    KVER_MARKER = ('https://chromium.googlesource.com/chromiumos/'
                   'third_party/kernel ')
    ST_START_MARKER = 'Call Trace:'

    def __init__(self, bugid, title):
        self.bugid = bugid
        self.title = title
        self.crashat = ''
        self.kernel = ''
        self.stacktrace = []
        self.parsebody()

    def __repr__(self):
        print(self.stacktrace)
        return ('bugid:%s title:"%s" crashat:%s kernel:%s\n'
                % (self.bugid, self.title, self.crashat, self.kernel))

    def setcrashat(self, line):
        """Sets the kernel commit at which this crash occured."""
        self.crashat = line.strip().split()[-1]

    def setkver(self, line):
        """Sets the kernel version for which this crash occured."""
        self.kernel = line.strip().split()[-1]

    def setst(self, st):
        """Sets the stacktrace associated with the Issuetracker bug.

        A bug might have multiple stacktraces. |st| is a list of set
        of strings, where each string is a function name in the stacktrace.
        """
        if not st:
            return
        self.stacktrace = st

    def parsebody(self):
        """Parse the body of an IssueTracker bug."""
        print('Bug = %s' % (self.bugid))
        cmd = Issuetracker.LIST_BUG_ASC % (self.bugid)
        bugbody = subprocess.check_output(cmd, shell=True).split('\n')

        for i, line in enumerate(bugbody):
            if IssuetrackerBug.COMMIT_MARKER in line:
                self.setcrashat(line)
            elif IssuetrackerBug.KVER_MARKER in line:
                self.setkver(line)
            elif IssuetrackerBug.ST_START_MARKER in line:
                self.setst(get_stacktrace(i, bugbody))
                break


class Issuetracker(object):
    """Issuetracker mananger a collection of chromeos IssuetrackerBug's."""
    LIST_ALL_BUGS = 'bugged hotlist %s'
    LIST_BUG_ASC = 'bugged show --sort=asc %s'

    def __init__(self, hotlistid):
        self.hotlistid = hotlistid
        self.bugs = []
        utils.rmfile_if_exists(config.ISSUETRACKER_DB)
        self.populate_bugs()
        self.db = simpledb.SimpleDB(config.ISSUETRACKER_DB)

    def populate_bugs(self):
        """Retrieve a list of all bugs in a hotlist and parse."""
        cmd = Issuetracker.LIST_ALL_BUGS % (self.hotlistid)
        all_bug_lines = subprocess.check_output(cmd, shell=True).split('\n')
        for i, line in enumerate(all_bug_lines[1:]):
            print(i)
            self.parse_bug_line(line)

    def parse_bug_line(self, line):
        """Parse the details of a bug from a list of bugs."""
        if not line.strip():
            return

        parts = line.split()
        bugid, status, title = parts[0], parts[7], ' '.join(parts[8:])
        if status != 'NEW':
            return

        b = IssuetrackerBug(bugid, title)
        self.bugs.append(b)

    def print_bugs(self):
        """Dump all parsed Issuetracker bugs for debugging."""
        for bug in self.bugs:
            print(bug)

    def save(self):
        """Save parsed Issuetracker bugs to a local cache."""
        self.db.begin()
        for bug in self.bugs:
            self.db.insert(bugid=bug.bugid, title=bug.title,
                           crashat=bug.crashat, kernel=bug.kernel,
                           stacktrace=base64.b64encode(
                               pickle.dumps(bug.stacktrace)))
        self.db.commit()
        print('[+] Done writing %d records to "%s"' % (len(self.bugs),
                                                       config.ISSUETRACKER_DB))
