#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Parse ChangeLog from CPCon and generate commit message.

Usage:
    1. Copy ChangeLog from CPCon (everything except the MENU bar)
    2. xsel -b | ./gen_uprev_msg.py [-b BOARD] [--extra-repo-file FILE]
    3. Commit message will be printed to stdout
    4. Be aware of the warning messages in stderr
"""
from __future__ import print_function

import argparse
import collections
import logging
import re
import sys

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

MAX_LENGTH = 72
CHANGES_PATTERN = r'Changes between ([0-9\.]+) and ([0-9\.]+)'

DEFAULT_REPOS = (
    'src/overlays',
    'src/platform/bmpblk',
    'src/platform/depthcharge',
    'src/platform/ec',
    'src/platform/firmware',
    'src/platform/vboot_reference',
    'src/third_party/arm-trusted-firmware',
    'src/third_party/chromiumos-overlay',
    'src/third_party/coreboot',
    'src/third_party/coreboot/3rdparty/blobs',
)


CL = collections.namedtuple('CL', ['commit', 'cl', 'bug', 'title'])


def read_extra_repos(filename):
    """Read extra repos from |filename|."""
    repos = set()
    with open(filename) as f:
        for line in f:
            repo = line.strip()
            if repo:
                repos.add(repo)
    return repos


def parse_cl(line):
    """Parse CL."""
    tokens = line.split('\t')
    if len(tokens) != 6:
        return None
    commit, cl, bug, _date, _author, title = tokens
    return CL(commit, int(cl) if cl else None, int(bug) if bug else None, title)


def main(args):
    """Parse ChangeLog and print commit message."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('-b', '--board')
    parser.add_argument('--extra-repo-file',
                        help='File containing extra repo names')
    args = parser.parse_args(args)
    board = args.board or 'BOARD'
    included_repos = set(DEFAULT_REPOS)
    if args.extra_repo_file:
        included_repos |= read_extra_repos(args.extra_repo_file)

    changes = False
    repos = []
    repo = None
    ignored_repos = []
    skipped_lines = []
    for line in sys.stdin:
        line = line.strip()

        # Parse "Changes between 12573.80.0 and 12573.88.0"
        if not changes:
            m = re.match(CHANGES_PATTERN, line)
            if m:
                groups = m.groups()
                if len(groups) == 2:
                    changes = groups
            continue

        # Parse repo
        tokens = line.split()
        if len(tokens) == 1 and '/' in tokens[0]:
            repo = tokens[0]
            if repo in included_repos:
                cl_list = []
                repos.append((repo, cl_list))
            else:
                ignored_repos.append(repo)
                repo = None
            continue

        # Parse CL
        if not repo:
            continue

        cl = parse_cl(line)
        if cl:
            cl_list.append(cl)
        else:
            skipped_lines.append(line)
            continue

    if not repos:
        logger.error('No repo found from ChangeLog')
        return 1

    # Output
    if changes:
        title = (f'chromeos-firmware-{board}: '
                 'Uprev firmware to {changes[1]} for {board}')
        print(title)
        print()

    print(f'Changes between {changes[0]} and {changes[1]}:')

    bugs = set()
    for repo, cl_list in repos:
        print()
        print(repo)
        private = 'private' in repo
        for cl in cl_list:
            if not cl.cl:
                continue
            cl_str = f'CL:*{cl.cl}' if private else f'CL:{cl.cl}'
            title_max_len = MAX_LENGTH - len(cl_str) - 1 - 4
            title = cl.title
            while len(title) > title_max_len:
                tokens = title.rsplit(None, 1)
                if len(tokens) <= 1:
                    break
                title = tokens[0]
            line = f' {cl_str}\t{title}'
            print(line)
            if cl.bug:
                bugs.add(cl.bug)

    print()
    print('BRANCH=none')
    bugs = [f'b:{bug}' if bug >= 1e8 else f'chromium:{bug}'
            for bug in sorted(bugs)]
    line_bugs = []
    length = len('BUG=')
    for bug in bugs:
        if line_bugs:
            bug = ', ' + bug
        if length + len(bug) <= MAX_LENGTH:
            line_bugs.append(bug)
            length += len(bug)
        else:
            print('BUG=' + ''.join(line_bugs))
            line_bugs = []
            length = 0
    if line_bugs:
        print('BUG=' + ''.join(line_bugs))
    print(f'TEST=emerge-{board} chromeos-firmware-{board}')

    # Warnings
    for repo in ignored_repos:
        logger.warning('Ignore repo %s', repo)
    for line in skipped_lines:
        logger.warning('Skipping line: %s', line)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
