#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a tool for picking patches from upstream and applying them."""

from __future__ import print_function

import ConfigParser
import argparse
import functools
import mailbox
import os
import pprint
import re
import signal
import subprocess
import sys
import textwrap
import urllib

errprint = functools.partial(print, file=sys.stderr)

LINUX_URLS = (
    'git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
    'https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
    'https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux.git',
)

COMMIT_MESSAGE_WIDTH = 75

_PWCLIENTRC = os.path.expanduser('~/.pwclientrc')

def _get_conflicts():
    """Report conflicting files."""
    resolutions = ('DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU')
    conflicts = []
    lines = subprocess.check_output(['git', 'status', '--porcelain',
                                     '--untracked-files=no']).split('\n')
    for line in lines:
        if not line:
            continue
        resolution, name = line.split(None, 1)
        if resolution in resolutions:
            conflicts.append('   ' + name)
    if not conflicts:
        return ''
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
            errprint('Found "%s".' % path)
            errprint(conflicts)
            errprint('Please resolve the conflicts and restart the '
                     'shell job when done. Kill this job if you '
                     'aborted the conflict.')
            os.kill(os.getpid(), signal.SIGTSTP)
    # TODO: figure out what the state is after the merging, and go based on
    # that (should we abort? skip? continue?)
    # Perhaps check last commit message to see if it's the one we were using.

def _get_pw_url(project):
    """Retrieve the patchwork server URL from .pwclientrc.

    Args:
        project: patchwork project name; if None, we retrieve the default
            from pwclientrc
    """
    config = ConfigParser.ConfigParser()
    config.read([_PWCLIENTRC])

    if project is None:
        try:
            project = config.get('options', 'default')
        except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
            errprint('Error: no default patchwork project found in %s.'
                     % _PWCLIENTRC)
            sys.exit(1)

    if not config.has_option(project, 'url'):
        errprint("Error: patchwork URL not found for project '%s'" % project)
        sys.exit(1)

    url = config.get(project, 'url')
    # Strip trailing 'xmlrpc' and/or trailing slash.
    return re.sub('/(xmlrpc/)?$', '', url)

def _wrap_commit_line(prefix, content):
    line = prefix + '=' + content
    indent = ' ' * (len(prefix) + 1)
    return textwrap.fill(line, COMMIT_MESSAGE_WIDTH, subsequent_indent=indent)

def _match_patchwork(match, args):
    """Match location: pw://### or pw://PROJECT/###."""
    pw_project = match.group(2)
    patch_id = int(match.group(3))

    if args['debug']:
        print('_match_patchwork: pw_project=%s, patch_id=%d' %
              (pw_project, patch_id))

    if args['tag'] is None:
        args['tag'] = 'FROMLIST: '

    url = _get_pw_url(pw_project)
    opener = urllib.urlopen('%s/patch/%d/mbox' % (url, patch_id))
    if opener.getcode() != 200:
        errprint('Error: could not download patch - error code %d'
                 % opener.getcode())
        sys.exit(1)
    patch_contents = opener.read()

    if not patch_contents:
        errprint('Error: No patch content found')
        sys.exit(1)

    if args['source_line'] is None:
        args['source_line'] = '(am from %s/patch/%d/)' % (url, patch_id)
        message_id = mailbox.Message(patch_contents)['Message-Id']
        message_id = re.sub('^<|>$', '', message_id.strip())
        args['source_line'] += (
            '\n(also found at https://lkml.kernel.org/r/%s)' % message_id)

    if args['replace']:
        subprocess.call(['git', 'reset', '--hard', 'HEAD~1'])

    git_am = subprocess.Popen(['git', 'am', '-3'], stdin=subprocess.PIPE)
    git_am.communicate(patch_contents)
    return git_am.returncode

def _match_linux(match, args):
    """Match location: linux://HASH."""
    commit = match.group(1)

    if args['debug']:
        print('_match_linux: commit=%s' % commit)

    # Confirm a 'linux' remote is setup.
    linux_remote = _find_linux_remote()
    if not linux_remote:
        errprint('Error: need a valid upstream remote')
        sys.exit(1)

    linux_master = '%s/master' % linux_remote
    ret = subprocess.call(['git', 'merge-base', '--is-ancestor',
                           commit, linux_master])
    if ret:
        errprint('Error: Commit not in %s' % linux_master)
        sys.exit(1)

    if args['source_line'] is None:
        git_pipe = subprocess.Popen(['git', 'rev-parse', commit],
                                    stdout=subprocess.PIPE)
        commit = git_pipe.communicate()[0].strip()

        args['source_line'] = ('(cherry picked from commit %s)' %
                               (commit))
    if args['tag'] is None:
        args['tag'] = 'UPSTREAM: '

    if args['replace']:
        subprocess.call(['git', 'reset', '--hard', 'HEAD~1'])

    return subprocess.call(['git', 'cherry-pick', commit])

def _match_fromgit(match, args):
    """Match location: git://remote/branch/HASH."""
    remote = match.group(2)
    branch = match.group(3)
    commit = match.group(4)

    if args['debug']:
        print('_match_fromgit: remote=%s branch=%s commit=%s' %
              (remote, branch, commit))

    ret = subprocess.call(['git', 'merge-base', '--is-ancestor',
                           commit, '%s/%s' % (remote, branch)])
    if ret:
        errprint('Error: Commit not in %s/%s' % (remote, branch))
        sys.exit(1)

    git_pipe = subprocess.Popen(['git', 'remote', 'get-url', remote],
                                stdout=subprocess.PIPE)
    url = git_pipe.communicate()[0].strip()

    if args['source_line'] is None:
        git_pipe = subprocess.Popen(['git', 'rev-parse', commit],
                                    stdout=subprocess.PIPE)
        commit = git_pipe.communicate()[0].strip()

        args['source_line'] = (
            '(cherry picked from commit %s\n %s %s)' % (commit, url, branch))
    if args['tag'] is None:
        args['tag'] = 'FROMGIT: '

    if args['replace']:
        subprocess.call(['git', 'reset', '--hard', 'HEAD~1'])

    return subprocess.call(['git', 'cherry-pick', commit])

def _match_gitfetch(match, args):
    """Match location: (git|https)://repoURL#branch/HASH."""
    remote = match.group(1)
    branch = match.group(3)
    commit = match.group(4)

    if args['debug']:
        print('_match_gitfetch: remote=%s branch=%s commit=%s' %
              (remote, branch, commit))

    ret = subprocess.call(['git', 'fetch', remote, branch])
    if ret:
        errprint('Error: Branch not in %s' % remote)
        sys.exit(1)

    url = remote

    if args['source_line'] is None:
        git_pipe = subprocess.Popen(['git', 'rev-parse', commit],
                                    stdout=subprocess.PIPE)
        commit = git_pipe.communicate()[0].strip()

        args['source_line'] = (
            '(cherry picked from commit %s\n %s %s)' % (commit, url, branch))
    if args['tag'] is None:
        args['tag'] = 'FROMGIT: '

    return subprocess.call(['git', 'cherry-pick', commit])

def main(args):
    """This is the main entrypoint for fromupstream.

    Args:
        args: sys.argv[1:]

    Returns:
        An int return code.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('--bug', '-b',
                        type=str, help='BUG= line')
    parser.add_argument('--test', '-t',
                        type=str, help='TEST= line')
    parser.add_argument('--crbug', action='append',
                        type=int, help='BUG=chromium: line')
    parser.add_argument('--buganizer', action='append',
                        type=int, help='BUG=b: line')
    parser.add_argument('--changeid', '-c',
                        help='Overrides the gerrit generated Change-Id line')

    parser.add_argument('--replace', '-r',
                        action='store_true',
                        help='Replaces the HEAD commit with this one, taking '
                        'its properties(BUG, TEST, Change-Id). Useful for '
                        'updating commits.')
    parser.add_argument('--nosignoff',
                        dest='signoff', action='store_false')
    parser.add_argument('--debug', '-d', action='store_true',
                        help='Prints more verbose logs.')

    parser.add_argument('--tag',
                        help='Overrides the tag from the title')
    parser.add_argument('--source', '-s',
                        dest='source_line', type=str,
                        help='Overrides the source line, last line, ex: '
                        '(am from http://....)')
    parser.add_argument('locations',
                        nargs='+',
                        help='Patchwork ID (pw://### or pw://PROJECT/###, '
                        'where PROJECT is defined in ~/.pwclientrc; if no '
                        'PROJECT is specified, the default is retrieved from '
                        '~/.pwclientrc), '
                        'linux commit like linux://HASH, or '
                        'git reference like git://remote/branch/HASH or '
                        'git://repoURL#branch/HASH or '
                        'https://repoURL#branch/HASH')

    args = vars(parser.parse_args(args))

    buglist = [args['bug']] if args['bug'] else []
    if args['buganizer']:
        buglist += ['b:{0}'.format(x) for x in args['buganizer']]
    if args['crbug']:
        buglist += ['chromium:{0}'.format(x) for x in args['crbug']]
    if buglist:
        args['bug'] = ', '.join(buglist)

    if args['replace']:
        old_commit_message = subprocess.check_output(
            ['git', 'show', '-s', '--format=%B', 'HEAD']
        ).strip('\n')

        # It is possible that multiple Change-Ids are in the commit message
        # (due to cherry picking).  We only want to pull out the first one.
        changeid_match = re.search('^Change-Id: (.*)$',
                                   old_commit_message, re.MULTILINE)
        if changeid_match:
            args['changeid'] = changeid_match.group(1)

        bugs = re.findall('BUG=(.*)$', old_commit_message, re.MULTILINE)
        if args['bug'] is None and bugs:
            args['bug'] = '\nBUG='.join(bugs)

        tests = re.findall('TEST=(.*)$', old_commit_message, re.MULTILINE)
        if args['test'] is None and tests:
            args['test'] = '\nTEST='.join(tests)
        # TODO: deal with multiline BUG/TEST better

    if args['bug'] is None or args['test'] is None:
        parser.error('BUG=/TEST= lines are required; --replace can help '
                     'automate, or set via --bug/--test')

    if args['debug']:
        pprint.pprint(args)

    re_matches = (
        (re.compile(r'pw://(([^/]+)/)?(\d+)'), _match_patchwork),
        (re.compile(r'linux://([0-9a-f]+)'), _match_linux),
        (re.compile(r'(from)?git://([^/\#]+)/([^#]+)/([0-9a-f]+)$'),
         _match_fromgit),
        (re.compile(r'((git|https)://.+)#(.+)/([0-9a-f]+)$'), _match_gitfetch),
    )

    for location in args['locations']:
        if args['debug']:
            print('location=%s' % location)

        for reg, handler in re_matches:
            match = reg.match(location)
            if match:
                ret = handler(match, args)
                break
        else:
            errprint('Don\'t know what "%s" means.' % location)
            sys.exit(1)

        if ret != 0:
            conflicts = _get_conflicts()
            if args['tag'] == 'UPSTREAM: ':
                args['tag'] = 'BACKPORT: '
            else:
                args['tag'] = 'BACKPORT: ' + args['tag']
            _pause_for_merge(conflicts)
        else:
            conflicts = ''

        # extract commit message
        commit_message = subprocess.check_output(
            ['git', 'show', '-s', '--format=%B', 'HEAD']
        ).strip('\n')

        # Remove stray Change-Id, most likely from merge resolution
        commit_message = re.sub(r'Change-Id:.*\n?', '', commit_message)

        # Note the source location before tagging anything else
        commit_message += '\n' + args['source_line']

        # add automatic Change ID, BUG, and TEST (and maybe signoff too) so
        # next commands know where to work on
        commit_message += '\n'
        commit_message += conflicts
        commit_message += '\n' + 'BUG=' + args['bug']
        commit_message += '\n' + _wrap_commit_line('TEST', args['test'])
        if args['signoff']:
            extra = ['-s']
        else:
            extra = []
        subprocess.Popen(
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

        # commit everything
        subprocess.Popen(
            ['git', 'commit', '--amend', '-F', '-'], stdin=subprocess.PIPE
        ).communicate(commit_message)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
