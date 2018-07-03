# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Local cache generator for bugs on syzkaller.appspot.com."""

from __future__ import print_function

from bs4 import BeautifulSoup
import config
import requests
import simpledb
import utils

URL = 'https://syzkaller.appspot.com'
FIXED_URL = 'https://syzkaller.appspot.com/?fixed=upstream'


class SyzkallerWebBug(object):
    """SyzkallerWebBug represents parsed info from a syzkaller link."""
    OPEN, FIXED, MODERATION = 'OPEN', 'FIXED', 'MODERATION'

    def __init__(self, url, title, status='OPEN', commitmsg=''):
        self.url = url
        self.title = title
        self.status = status
        self.commitmsg = commitmsg
        self.stacktrace = ''

    def __repr__(self):
        return 'TITLE:"%s" URL:"%s" STATUS:"%s" FIX:"%s"' \
                % (self.title, self.url, self.status, self.commitmsg)

    def find_fix(self):
        """Find the commit-fix for a syzkaller issue."""
        print('Title:"%s"' % (self.title))
        print('URL:"%s"' % (self.url))
        blob = requests.get(URL + self.url)
        text = blob.text
        self.commitmsg = text[text.find('Commits:'):].split('<br>')[0]
        self.commitmsg = self.commitmsg[len('Commits: '):]
        self.commitmsg = utils.clean_webcontent(self.commitmsg)
        print('Commitmsg:"%s"' % (repr(self.commitmsg)))
        try:
            ta_start = ('<textarea id="log_textarea" readonly rows="25" '
                        'wrap=off>')
            ta_end = '</textarea>'
            self.stacktrace = text.split(ta_start)[1]
            self.stacktrace = self.stacktrace[:self.stacktrace.find(ta_end)]
            self.stacktrace = utils.clean_webcontent(self.stacktrace)
        except IndexError, _:
            print(('[x] Unable to find stacktrace on syzweb for url:"%s"'
                   % (self.url)))


class SyzkallerWeb(object):
    """SyzkallerWeb is a collection of SyzkallerWebBug objects."""
    def __init__(self, fromdb=False):
        self.swbugs = set()
        self.count_nost = 0
        if not fromdb:
            self._init_bugs()
        self.db = simpledb.SimpleDB(config.SYZWEB_DB)

    def _init_bugs(self):
        """Fetch fixed syzkaller bugs from syzkaller.appspot.com."""
        blob = requests.get(FIXED_URL)
        soup = BeautifulSoup(blob.text, 'html.parser')
        for i in soup.find_all('tr'):
            url = i.find('a').get('href')
            title = i.find('a').text

            if title in ['Title', 'syzbot']:
                continue

            s = SyzkallerWebBug(url, title)
            self.swbugs.add(s)

        for swbug in self.swbugs:
            swbug.find_fix()
            if not swbug.stacktrace:
                self.count_nost += 1
        print('Unable to find stacktraces for %d swbugs' % (self.count_nost))

    def save(self):
        """Save parsed syzkaller bugs to a local cache."""
        self.db.begin()
        for swbug in self.swbugs:
            self.db.insert(url=swbug.url,
                           title=swbug.title,
                           commitmsg=swbug.commitmsg,
                           stacktrace=swbug.stacktrace)
        self.db.commit()
        print('[+] Done writing %d records to %s' % (len(self.swbugs),
                                                     config.SYZWEB_DB))
