# -*- coding: utf-8 -*-
# Copyright 2018 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities to parse and cache git repository logs."""

from __future__ import print_function

import base64

import simpledb
import utils


class Gitcommit(object):
    """Gitcommit represents a parsed git commit message."""
    def __init__(self, commitid, title, body, files=''):
        self.commitid = commitid
        self.title = title
        self.body = body
        self.files = files.strip()

    def __repr__(self):
        return '%s: %s' % (self.commitid, self.title)


class Gitlog(object):
    """Gitlog reads and parses a gitlog into Gitcommit objects."""
    def __init__(self, filename, dbname):
        self.filename = filename
        self.dbname = dbname
        self.commits = []
        self.contents = open(self.filename).readlines()

        utils.rmfile_if_exists(self.dbname)
        self.parse_log()
        self.db = simpledb.SimpleDB(dbname)

    def parse_log(self):
        """Parse the output of 'git log'."""
        i = 0
        is_commit_start = lambda x: x.startswith('commit')
        is_merge_commit = lambda x: x.startswith('Merge:')

        while i < len(self.contents):
            if is_commit_start(self.contents[i]):
                if is_merge_commit(self.contents[i+1]):
                    i += 1
                    continue

                commitid = self.contents[i].split()[1]

                i += 4
                title = self.contents[i].strip()
                title = utils.clean_git_title(title)

                i += 2
                body = ''
                while (i < len(self.contents) and not
                       is_commit_start(self.contents[i])):
                    if not self.contents[i].startswith(' '):
                        i += 1
                        break
                    body += self.contents[i].strip() + '\n'
                    i += 1

                files = ''
                while (i < len(self.contents) and not
                       is_commit_start(self.contents[i])):
                    if not self.contents[i].strip():
                        i += 1
                        continue
                    files += self.contents[i]
                    i += 1

                gc = Gitcommit(commitid, title, body, files)
                self.commits.append(gc)
                continue
            i += 1

    def save(self):
        """Saves parsed git commits into a local cache."""
        print("Starting to save %d records" % (len(self.commits)))
        i = 0
        self.db.begin()
        for commit in self.commits:
            self.db.insert(commitid=commit.commitid, title=commit.title,
                           body=base64.b64encode(commit.body),
                           files=base64.b64encode(commit.files))
            i += 1
            if i % 100000 == 0:
                print('---', i)
        self.db.commit()
        print('[+] Done writing %d records to "%s"' % (len(self.commits),
                                                       self.dbname))
