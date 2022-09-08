#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Handle topics"""

from __future__ import print_function
import sqlite3
import os
from config import topiclist
from common import rebasedb

topics = []

def get_topic(filename, n=None):
    """Return topic associated with filename, or 0 if not found"""

    for (subdir, topic, name,) in topics:
        if filename and filename.startswith(subdir):
            return topic
        if n and n == name:
            return topic
    return 0


conn = sqlite3.connect(rebasedb)
c = conn.cursor()


def update_sha(sha, topic, filename='', base=''):
    """Update topic intormation for given SHA in database"""

    filelist = [(sha, topic, filename, base)]
    count = 0
    while filelist:
        (sha, topic, filename, base) = filelist.pop(0)
        c.execute(
            "select disposition, reason, topic from commits where sha is '%s' order by date"
            % (sha))
        result = c.fetchone()
        if result:
            disposition = result[0]
            reason = result[1]
            t = result[2]
            # Generate topic even if disposition is drop. We'll need it for statistics.
            # Do not look into stable release and android patches since those will always
            # be dropped.
            if disposition == 'drop' and reason in ('stable', 'android', 'Intel'):
                print("Disposition for '%s' is '%s' ('%s'), skipping" %
                      (sha, disposition, reason))
                return count

            # if (disposition == 'drop' and reason != 'revisit' and reason != 'revisit/fixup'
            #                       and reason != 'upstream/fixup' and reason != 'reverted'):
            #    print("Disposition for '%s' is '%s' ('%s'), skipping" % (sha,
            #          disposition, reason))
            #    return count
            if t != 0:
                if t != topic:
                    if filename != '':
                        print(
                            "topic already set to %d for sha '%s' [%s], skipping"
                            % (t, sha, filename))
                    else:
                        print(
                            "topic already set to %d for sha '%s' [none], skipping"
                            % (t, sha))
                return count
        else:
            print("No entry for sha '%s' found in database" % sha)
            return count
        print("  Adding sha '%s' to topic %d [%s]" % (sha, topic, filename))
        c.execute("UPDATE commits SET topic=%d where sha='%s'" % (topic, sha))
        count += 1
        # print("Attached SHA '%s' to topic %d" % (sha, topic))
        # Attach all SHAs touching the same set of files to the same topic.
        c.execute("select filename from files where sha is '%s'" % (sha))
        for (db_filename,) in c.fetchall():
            c.execute("select sha from files where filename is '%s'" %
                      (db_filename))
            for (fsha,) in c.fetchall():
                # print("Expect to attach sha '%s' to topic %d, file='%s'" %
                #       (fsha, topic, db_filename))
                if fsha != sha and not db_filename.endswith(
                        'Makefile') and not db_filename.endswith('Kconfig'):
                    if base != '' and not db_filename.startswith(
                            base) and get_topic(db_filename) != topic:
                        print("  Skipping '%s': base '%s' mismatch [%d-%d]" %
                              (db_filename, base, topic, get_topic(db_filename)))
                        continue
                    filelist.append([fsha, topic, db_filename, base])
    return count


def handle_topic(topic, subdir, name):
    """Handle one topic"""

    count = 0
    c.execute('select topic from topics where topic is %d' % topic)
    if not c.fetchone():
        print("Adding topic %d (%s), subdirectory/file '%s' to database" %
              (topic, name, subdir))
        c.execute('INSERT INTO topics(topic, name) VALUES (?, ?)', (
            topic,
            name,
        ))
    print("Handling topic %d (%s), subdirectory/file '%s'" %
          (topic, name, subdir))
    c.execute("select sha, filename from files where filename like '%s%%'" %
              subdir)
    for (sha, filename,) in c.fetchall():
        if filename.startswith(subdir):
            count += update_sha(sha, topic, filename, subdir)
    print('Topic %d (%s): %d entries' % (topic, name, count))


def handle_topics():
    """Main code"""

    global topics # pylint: disable=global-statement

    c.execute('select sha from commits order by date')
    for (sha,) in c.fetchall():
        c.execute("UPDATE commits SET topic=0 where sha='%s'" % sha)

    topic = 1
    topics = []
    for [name, subdirs] in topiclist:
        for subdir in subdirs:
            topics.append((subdir, topic, name))
        topic = topic + 1

    for (subdir, topic, name,) in topics:
        handle_topic(topic, subdir, name)

    topic = topic + 1

    # Identify left-over commits and assign dynamic topics.
    # This time skip entries with disposition=drop; we don't want
    # to create additional topics for those.

    while True:
        print('Topic %d' % topic)
        c.execute(
            "select sha from commits where topic=0 and disposition <> 'drop' order by date"
        )
        # c.execute("select sha from commits where topic=0 order by date")
        sha = c.fetchone()
        if sha:
            c.execute("select filename from files where sha is '%s'" % (sha[0]))
            files = c.fetchone()
            filename = ''
            subdir = ''
            if files:
                # Try to find a directory name outside include and Documentation
                # and use it as file and base (topic)
                filename = files[0] + '+'
                subdir = os.path.dirname(files[0])
                while files and (files[0].startswith('Documentation') or
                                 files[0].endswith('.h') or subdir == ''):
                    files = c.fetchone()
                    if files and not files[0].startswith('Documentation') \
                             and not files[0].endswith('.h') \
                             and os.path.dirname(files[0]) != '':
                        filename = files[0] + '+'
                        subdir = os.path.dirname(files[0])
            # Based on a sha, we found a file and subdirectory. Use it to attach
            # any matching SHAs to this subdirectory if the match is in a source
            # directory.
            print('Topic %d [%s, subdir %s]' % (topic, filename, subdir))
            if subdir.startswith('include') or subdir.startswith(
                    'Documentation') or subdir == '':
                count = update_sha(sha[0], topic, filename, subdir)
                print('Topic %d [%s]: %d entries' % (topic, filename, count))
            else:
                t = get_topic(None, subdir)
                if t:
                    handle_topic(t, subdir, subdir)
                else:
                    topics.append((subdir, topic, subdir))
                    handle_topic(topic, subdir, subdir)
        else:
            break
        topic = topic + 1

    conn.commit()
    conn.close()

if __name__ == '__main__':
    handle_topics()
