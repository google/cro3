#!/usr/bin/env python2
#
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This is a tool for picking patches from upstream and applying them."""

from __future__ import print_function

import argparse
import os
import re
import signal
import subprocess
import sys

LINUX_URLS = (
    'git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
    'https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
    'https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux.git',
)

def _get_conflicts():
    """Report conflicting files."""
    resolutions = ('DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU')
    conflicts = []
    files = subprocess.check_output(['git', 'status', '--porcelain',
                                     '--untracked-files=no']).split('\n')
    for file in files:
        if not file:
            continue
        resolution, name = file.split(None, 1)
        if resolution in resolutions:
            conflicts.append('   ' + name)
    if not conflicts:
        return ""
    return '\nConflicts:\n%s\n' % '\n'.join(conflicts)

def _find_linux_remote():
    """Find a remote pointing to a Linux upstream repository."""
    git_remote = subprocess.Popen(['git', 'remote'], stdout=subprocess.PIPE)
    remotes = git_remote.communicate()[0].strip()
    for remote in remotes.splitlines():
        rurl = subprocess.Popen(['git', 'remote', 'get-url', remote],
                                stdout=subprocess.PIPE)
        url = rurl.communicate()[0].strip()
        if not rurl.returncode and url in LINUX_URLS:
            return remote
    return None

def _pause_for_merge(conflicts):
    """Pause and go in the background till user resolves the conflicts."""

    git_root = subprocess.check_output(['git', 'rev-parse',
                                        '--show-toplevel']).strip('\n')

    paths = (
        os.path.join(git_root, '.git', 'rebase-apply'),
        os.path.join(git_root, '.git', 'CHERRY_PICK_HEAD'),
    )
    for path in paths:
        if os.path.exists(path):
            sys.stderr.write('Found "%s".\n' % path)
            sys.stderr.write(conflicts)
            sys.stderr.write('Please resolve the conflicts and restart the ' +
                             'shell job when done. Kill this job if you ' +
                             'aborted the conflict.\n')
            os.kill(os.getpid(), signal.SIGTSTP)
    # TODO: figure out what the state is after the merging, and go based on
    # that (should we abort? skip? continue?)
    # Perhaps check last commit message to see if it's the one we were using.

def main(args):
    """This is the main entrypoint for fromupstream.

    Args:
        args: sys.argv[1:]

    Returns:
        An int return code.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('--bug', '-b',
                        type=str, default='None', help='BUG= line')
    parser.add_argument('--test', '-t',
                        type=str, default='Build and boot', help='TEST= line')
    parser.add_argument('--changeid', '-c',
                        help='Overrides the gerrit generated Change-Id line')

    parser.add_argument('--replace',
                        action='store_true',
                        help='Replaces the HEAD commit with this one, taking ' +
                        'its properties(BUG, TEST, Change-Id). Useful for ' +
                        'updating commits.')
    parser.add_argument('--nosignoff',
                        dest='signoff', action='store_false')

    parser.add_argument('--tag',
                        help='Overrides the tag from the title')
    parser.add_argument('--source', '-s',
                        dest='source_line', type=str,
                        help='Overrides the source line, last line, ex: ' +
                        '(am from http://....)')
    parser.add_argument('locations',
                        nargs='*',
                        help='Patchwork url (either ' +
                        'https://patchwork.kernel.org/patch/###/ or ' +
                        'pw://###), linux commit like linux://HASH, git ' +
                        'refrerence like fromgit://remote/branch/HASH')

    args = vars(parser.parse_args(args))

    if args['replace']:
        old_commit_message = subprocess.check_output(
            ['git', 'show', '-s', '--format=%B', 'HEAD']
        ).strip('\n')
        args['changeid'] = re.findall('Change-Id: (.*)$',
                                      old_commit_message, re.MULTILINE)[0]
        if args['bug'] == parser.get_default('bug'):
            args['bug'] = '\nBUG='.join(re.findall('BUG=(.*)$',
                                                   old_commit_message,
                                                   re.MULTILINE))
        if args['test'] == parser.get_default('test'):
            args['test'] = '\nTEST='.join(re.findall('TEST=(.*)$',
                                                     old_commit_message,
                                                     re.MULTILINE))
        # TODO: deal with multiline BUG/TEST better
        subprocess.call(['git', 'reset', '--hard', 'HEAD~1'])

    while len(args['locations']) > 0:
        location = args['locations'].pop(0)

        patchwork_match = re.match(
            r'((pw://)|(https?://patchwork.kernel.org/patch/))(\d+)/?', location
        )
        linux_match = re.match(
            r'linux://([0-9a-f]+)', location
        )
        fromgit_match = re.match(
            r'fromgit://([^/]+)/(.+)/([0-9a-f]+)$', location
        )

        if patchwork_match is not None:
            patch_id = int(patchwork_match.group(4))

            if args['source_line'] is None:
                args['source_line'] = \
                    '(am from https://patchwork.kernel.org/patch/%d/)' % \
                    patch_id
            if args['tag'] is None:
                args['tag'] = 'FROMLIST: '

            pw_pipe = subprocess.Popen(['pwclient', 'view', str(patch_id)],
                                       stdout=subprocess.PIPE)
            s = pw_pipe.communicate()[0]

            if not s:
                sys.stderr.write('Error: No patch content found\n')
                sys.exit(1)
            git_am = subprocess.Popen(['git', 'am', '-3'], stdin=subprocess.PIPE)
            git_am.communicate(unicode(s).encode('utf-8'))
            ret = git_am.returncode
        elif linux_match:
            commit = linux_match.group(1)

            # Confirm a 'linux' remote is setup.
            linux_remote = _find_linux_remote()
            if not linux_remote:
                sys.stderr.write('Error: need a valid upstream remote\n')
                sys.exit(1)

            linux_master = '%s/master' % linux_remote
            ret = subprocess.call(['git', 'merge-base', '--is-ancestor',
                                   commit, linux_master])
            if ret:
                sys.stderr.write('Error: Commit not in %s\n' % linux_master)
                sys.exit(1)

            if args['source_line'] is None:
                git_pipe = subprocess.Popen(['git', 'rev-parse', commit],
                                            stdout=subprocess.PIPE)
                commit = git_pipe.communicate()[0].strip()

                args['source_line'] = ('(cherry picked from commit %s)' %
                                       (commit))
            if args['tag'] is None:
                args['tag'] = 'UPSTREAM: '

            ret = subprocess.call(['git', 'cherry-pick', commit])
        elif fromgit_match is not None:
            remote = fromgit_match.group(1)
            branch = fromgit_match.group(2)
            commit = fromgit_match.group(3)

            ret = subprocess.call(['git', 'merge-base', '--is-ancestor',
                                   commit, '%s/%s' % (remote, branch)])
            if ret:
                sys.stderr.write('Error: Commit not in %s/%s\n' %
                                 (remote, branch))
                sys.exit(1)

            git_pipe = subprocess.Popen(['git', 'remote', 'get-url', remote],
                                        stdout=subprocess.PIPE)
            url = git_pipe.communicate()[0].strip()

            if args['source_line'] is None:
                git_pipe = subprocess.Popen(['git', 'rev-parse', commit],
                                            stdout=subprocess.PIPE)
                commit = git_pipe.communicate()[0].strip()

                args['source_line'] = \
                    '(cherry picked from commit %s\n %s %s)' % \
                    (commit, url, branch)
            if args['tag'] is None:
                args['tag'] = 'FROMGIT: '

            ret = subprocess.call(['git', 'cherry-pick', commit])
        else:
            sys.stderr.write('Don\'t know what "%s" means.\n' % location)
            sys.exit(1)

        if ret != 0:
            conflicts = _get_conflicts()
            args['tag'] = 'BACKPORT: '
            _pause_for_merge(conflicts)
        else:
            conflicts = ""

        # extract commit message
        commit_message = subprocess.check_output(
            ['git', 'show', '-s', '--format=%B', 'HEAD']
        ).strip('\n')

        # add automatic Change ID, BUG, and TEST (and maybe signoff too) so
        # next commands know where to work on
        commit_message += '\n'
        commit_message += conflicts
        commit_message += '\n' + 'BUG=' + args['bug']
        commit_message += '\n' + 'TEST=' + args['test']
        if args['signoff']:
            extra = ['-s']
        else:
            extra = []
        commit = subprocess.Popen(
            ['git', 'commit'] + extra + ['--amend', '-F', '-'],
            stdin=subprocess.PIPE
        ).communicate(commit_message)

        # re-extract commit message
        commit_message = subprocess.check_output(
            ['git', 'show', '-s', '--format=%B', 'HEAD']
        ).strip('\n')

        # replace changeid if needed
        if args['changeid'] is not None:
            commit_message = re.sub(r'(Change-Id: )(\w+)', r'\1%s' %
                                    args['changeid'], commit_message)
            args['changeid'] = None

        # decorate it that it's from outside
        commit_message = args['tag'] + commit_message
        commit_message += '\n' + args['source_line']

        # commit everything
        commit = subprocess.Popen(
            ['git', 'commit', '--amend', '-F', '-'], stdin=subprocess.PIPE
        ).communicate(commit_message)

        return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
