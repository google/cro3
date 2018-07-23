#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Autotriager."""

from __future__ import print_function

import argparse
import base64
import pickle
import sys

import config
import simpledb
import utils

REPORT_TEMPLATE = """
Upstream commit is %s ("%s").

%s
%s

Syzkaller URL with a similar report is at %s
"""


class AutoTriager(object):
    """Autotriager triages syzkaller bugs on issuetracker.

    AutoTriager correlates information from issuetracker and
    syzweb to determine fixes for issuetracker bugs.
    """
    def __init__(self):
        self._use_mst = False
        self.it_db = simpledb.SimpleDB(config.ISSUETRACKER_DB)
        self.syz_db = simpledb.SimpleDB(config.SYZWEB_DB)
        self.linux_db = simpledb.SimpleDB(config.SRC_LINUX_DB)
        self.cros_dbs = (
            simpledb.SimpleDB(config.SRC_V414_DB),
            simpledb.SimpleDB(config.SRC_V44_DB),
            simpledb.SimpleDB(config.SRC_V318_DB),
            simpledb.SimpleDB(config.SRC_V314_DB),
            simpledb.SimpleDB(config.SRC_V310_DB),
            simpledb.SimpleDB(config.SRC_V38_DB),
        )

        try:
            self.triaged_bugs = open('triaged_bugs').readlines()
            self.triaged_bugs = [i.strip() for i in self.triaged_bugs]
        except IOError as _:
            self.triaged_bugs = []

        try:
            contents = open('blacklistfns').readlines()
            contents = [i for i in contents if not i.startswith('#')]
            self.blacklistfns = set([i.strip() for i in contents])
        except IOError as _:
            self.blacklistfns = []

        try:
            contents = open('known_mismatch', 'r').readlines()
            contents = [i.strip().split() for i in contents]
            self.known_mismatch = {i[0]:i[1] for i in contents}
        except IOError as _:
            self.known_mismatch = {}

        print('[+] Autotriager initialized.')

    def use_mst(self):
        """Set Autotriager to use stacktrace matching."""
        self._use_mst = True

    def is_triaged(self, bugid):
        """Returns true if bugid if listed as already triaged."""
        return bugid in self.triaged_bugs

    def is_mismatch(self, bugid, url):
        """Returns true if |url| is known to not be the fix for |bugid|."""
        return self.known_mismatch.get(bugid, '') == url

    def generate_report(self, cid, cmsg, url):
        """Generate a report with commit information.

        Generate a report indicating which kernels the commit is
        present in, and which syzweb report was used to find the commit.
        """
        patch_status = [0] * len(self.cros_dbs)
        for i, crosdb in enumerate(self.cros_dbs):
            if crosdb.find_one(title=cmsg):
                patch_status[i] = 1
                continue

        VERSIONS = ['v4.14', 'v4.4', 'v3.18', 'v3.14', 'v3.10', 'v3.8']
        present = [VERSIONS[i] for i, j in enumerate(patch_status) if j]
        not_present = [VERSIONS[i] for i, j in enumerate(patch_status) if not j]

        present = ','.join(present)
        not_present = ','.join(not_present)

        if present:
            present = 'This patch is present in ' + present
        if not_present:
            not_present = 'This patch is not present in ' + not_present

        url = 'https://syzkaller.appspot.com' + url
        report = REPORT_TEMPLATE % (cid[:12], cmsg, present, not_present, url)

        utils.print_report(report)

    def clear_blacklistedfns(self, st):
        """Filter functions that are blacklisted."""
        return set(i for i in st if i not in self.blacklistfns)

    def matchstacktrace(self, itbug_sts, syz_st):
        """Match stacktraces obtained from syzweb and issuetracker."""
        if not self._use_mst:
            return True

        count = 0
        itbug_sts = pickle.loads(base64.b64decode(itbug_sts))
        for itbug_st in itbug_sts:
            count = 0
            itbug_st = self.clear_blacklistedfns(itbug_st)
            if len(itbug_st) < 3:
                continue
            for fn in itbug_st:
                if fn in syz_st:
                    count += 1
            if count == len(itbug_st):
                print('Match found using :-')
                print(itbug_st)
                return True
        return False

    def add_to_triaged(self, bugid):
        """Add |bugid| to the list of triaged bugs."""
        self.triaged_bugs.append(bugid)
        open('triaged_bugs', 'a').write(bugid+'\n')

    def add_mismatch(self, bugid, syzurl):
        """Avoid false positives in the future with |bugid| and |syzurl|."""
        self.known_mismatch[bugid] = syzurl
        open('known_mismatch', 'a').write('%s %s\n' %(bugid, syzurl))

    def _triage(self, title):
        """Correlate issuetracker against syzweb for a bug |title|."""
        it_bugs = self.it_db.find(title=title)
        syz_bugs = self.syz_db.find(title=title)

        for itbug in it_bugs:
            for syzbug in syz_bugs:
                if not self.matchstacktrace(itbug['stacktrace'],
                                            syzbug['stacktrace']):
                    continue

                if self.is_triaged(itbug['bugid']):
                    continue

                if self.is_mismatch(itbug['bugid'], syzbug['url']):
                    continue

                utils.hit_summary(itbug['bugid'], syzbug['url'],
                                  syzbug['commitmsg'])

                if utils.interact('Generate report? [y/N] - '):
                    cid = self.linux_db.find_one(title=syzbug['commitmsg'])
                    cid = cid['commitid'] if cid else ''
                    self.generate_report(cid, syzbug['commitmsg'],
                                         syzbug['url'])
                    self.add_to_triaged(itbug['bugid'])

                else:
                    self.add_mismatch(itbug['bugid'], syzbug['url'])

                utils.endbanner()

    def triage(self):
        """Start autotriage using local caches."""
        common_titles = set()
        for it_bug in self.it_db.distinct('title'):
            it_title = it_bug['title']
            for match_syzbug in self.syz_db.find(title=it_title):
                common_titles.add(match_syzbug['title'])
        print('[+] %d common titles found' % (len(common_titles)))

        for title in common_titles:
            self._triage(title)
        print('[+] Autotriager done.')


def get_parser():
    """Create and return an ArgumentParser instance."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mst', action='store_true',
                        help='match stacktraces to determine if '
                             'the issuetracker bug and syzweb fix '
                             'match')
    return parser


def main(argv):
    """main."""
    a = AutoTriager()
    parser = get_parser()
    opts = parser.parse_args(argv)

    if opts.mst:
        a.use_mst()

    a.triage()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
