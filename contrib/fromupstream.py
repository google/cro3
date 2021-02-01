#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This is a tool for picking patches from upstream and applying them."""

import argparse
from collections import OrderedDict
import configparser
import functools
import mailbox
import os
import pprint
import re
import signal
import socket
import ssl
import subprocess
import sys
import textwrap
import urllib.request
import xmlrpc.client

errprint = functools.partial(print, file=sys.stderr)

# pylint: disable=line-too-long
# Note: Do not include trailing / in any of these
UPSTREAM_URLS = (
    # Acceptable Linux URLs
    'git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
    'https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
    'https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux.git',

    # Acceptible Linux Firmware URLs
    'git://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git',
    'https://git.kernel.org/pub/scm/linux/kernel/git/firmware/linux-firmware.git',
    'https://kernel.googlesource.com/pub/scm/linux/kernel/git/firmware/linux-firmware.git',

    # Upstream for various other projects
    'git://w1.fi/srv/git/hostap.git',
    'git://git.kernel.org/pub/scm/bluetooth/bluez.git',
    'https://github.com/andersson/qrtr.git',
    'https://review.coreboot.org/flashrom.git'
)

PATCHWORK_URLS = (
    'https://lore.kernel.org/patchwork',
    'https://patchwork.kernel.org',
    'https://patchwork.ozlabs.org',
    'https://patchwork.freedesktop.org',
)

COMMIT_MESSAGE_WIDTH = 75

_PWCLIENTRC = os.path.expanduser('~/.pwclientrc')

def _git(args, stdin=None, encoding='utf-8', no_stderr=False):
    """Calls a git subcommand.

    Similar to subprocess.check_output.

    Args:
        args: subcommand + args passed to 'git'.
        stdin: a string or bytes (depending on encoding) that will be passed
            to the git subcommand.
        encoding: either 'utf-8' (default) or None. Override it to None if
            you want both stdin and stdout to be raw bytes.
        no_stderr: If True, we'll eat stderr

    Returns:
        the stdout of the git subcommand, same type as stdin. The output is
        also run through strip to make sure there's no extra whitespace.

    Raises:
        subprocess.CalledProcessError: when return code is not zero.
            The exception has a .returncode attribute.
    """
    return subprocess.run(
        ['git'] + args,
        encoding=encoding,
        input=stdin,
        stdout=subprocess.PIPE,
        stderr=(subprocess.PIPE if no_stderr else None),
        check=True,
    ).stdout.strip()

def _git_returncode(*args, **kwargs):
    """Same as _git, but return returncode instead of stdout.

    Similar to subprocess.call.

    Never raises subprocess.CalledProcessError.
    """
    try:
        _git(*args, **kwargs)
        return 0
    except subprocess.CalledProcessError as e:
        return e.returncode

def _get_conflicts():
    """Report conflicting files."""
    resolutions = ('DD', 'AU', 'UD', 'UA', 'DU', 'AA', 'UU')
    conflicts = []
    output = _git(['status', '--porcelain', '--untracked-files=no'])
    for line in output.splitlines():
        if not line:
            continue
        resolution, name = line.split(None, 1)
        if resolution in resolutions:
            conflicts.append('   ' + name)
    if not conflicts:
        return ''
    return '\nConflicts:\n%s\n' % '\n'.join(conflicts)

def _find_upstream_remote(urls):
    """Find a remote pointing to an upstream repository."""
    for remote in _git(['remote']).splitlines():
        try:
            if _git(['remote', 'get-url', remote]).rstrip('/') in urls:
                return remote
        except subprocess.CalledProcessError:
            # Kinda weird, get-url failing on an item that git just gave us.
            continue
    return None

def _pause_for_merge(conflicts):
    """Pause and go in the background till user resolves the conflicts."""

    git_root = _git(['rev-parse', '--show-toplevel'])
    previous_head_hash = _git(['rev-parse', 'HEAD'])

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

    # Check the conflicts actually got resolved. Otherwise we'll end up
    # modifying the wrong commit message and probably confusing people.
    while previous_head_hash == _git(['rev-parse', 'HEAD']):
        errprint('Error: no new commit has been made. Did you forget to run '
                 '`git am --continue` or `git cherry-pick --continue`?')
        errprint('Please create a new commit and restart the shell job (or kill'
                 ' it if you aborted the conflict).')
        os.kill(os.getpid(), signal.SIGTSTP)

def _get_pw_url(project):
    """Retrieve the patchwork server URL from .pwclientrc.

    Args:
        project: patchwork project name; if None, we retrieve the default
            from pwclientrc
    """
    config = configparser.ConfigParser()
    config.read([_PWCLIENTRC])

    if project is None:
        try:
            project = config.get('options', 'default')
        except (configparser.NoSectionError, configparser.NoOptionError) as e:
            errprint('Error: no default patchwork project found in %s. (%r)'
                     % (_PWCLIENTRC, e))
            sys.exit(1)

    if not config.has_option(project, 'url'):
        errprint("Error: patchwork URL not found for project '%s'" % project)
        sys.exit(1)

    url = config.get(project, 'url')
    # Strip trailing 'xmlrpc' and/or trailing slash.
    return re.sub('/(xmlrpc/)?$', '', url)

def _wrap_commit_line(prefix, content):
    line = prefix + content
    indent = ' ' * len(prefix)

    ret = textwrap.fill(line, COMMIT_MESSAGE_WIDTH, subsequent_indent=indent)
    return ret[len(prefix):]

def _pick_patchwork(url, patch_id, args):
    if args['tag'] is None:
        args['tag'] = 'FROMLIST: '

    try:
        opener = urllib.request.urlopen('%s/patch/%s/mbox' % (url, patch_id))
    except urllib.error.HTTPError as e:
        errprint('Error: could not download patch: %s' % e)
        sys.exit(1)
    patch_contents = opener.read()

    if not patch_contents:
        errprint('Error: No patch content found')
        sys.exit(1)

    message_id = mailbox.Message(patch_contents)['Message-Id']
    message_id = re.sub('^<|>$', '', message_id.strip())
    if args['source_line'] is None:
        args['source_line'] = '(am from %s/patch/%s/)' % (url, patch_id)
        for url_template in [
            'https://lore.kernel.org/r/%s',
            # hostap project (and others) are here, but not kernel.org.
            'https://marc.info/?i=%s',
            # public-inbox comes last as a "default"; it has a nice error page
            # pointing to other redirectors, even if it doesn't have what
            # you're looking for directly.
            'https://public-inbox.org/git/%s',
        ]:
            alt_url = url_template % message_id
            if args['debug']:
                print('Probing archive for message at: %s' % alt_url)
            try:
                urllib.request.urlopen(alt_url)
            except urllib.error.HTTPError as e:
                # Skip all HTTP errors. We can expect 404 for archives that
                # don't have this MessageId, or 300 for public-inbox ("not
                # found, but try these other redirects"). It's less clear what
                # to do with transitory (or is it permanent?) server failures.
                if args['debug']:
                    print('Skipping URL %s, error: %s' % (alt_url, e))
                continue
            # Success!
            if args['debug']:
                print('Found at %s' % alt_url)
            break
        else:
            errprint(
                "WARNING: couldn't find working MessageId URL; "
                'defaulting to "%s"' % alt_url)
        args['source_line'] += '\n(also found at %s)' % alt_url

    # Auto-snarf the Change-Id if it was encoded into the Message-Id.
    mo = re.match(r'.*(I[a-f0-9]{40})@changeid$', message_id)
    if mo and args['changeid'] is None:
        args['changeid'] = mo.group(1)

    if args['replace']:
        _git(['reset', '--hard', 'HEAD~1'])

    return _git_returncode(['am', '-3'], stdin=patch_contents, encoding=None)

def _match_patchwork(match, args):
    """Match location: pw://### or pw://PROJECT/###."""
    pw_project = match.group(2)
    patch_id = match.group(3)

    if args['debug']:
        print('_match_patchwork: pw_project=%s, patch_id=%s' %
              (pw_project, patch_id))

    url = _get_pw_url(pw_project)
    return _pick_patchwork(url, patch_id, args)

def _match_msgid(match, args):
    """Match location: msgid://MSGID."""
    msgid = match.group(1)

    if args['debug']:
        print('_match_msgid: message_id=%s' % (msgid))

    # Patchwork requires the brackets so force it
    msgid = '<' + msgid + '>'
    url = None
    for url in PATCHWORK_URLS:
        rpc = xmlrpc.client.ServerProxy(url + '/xmlrpc/')
        try:
            res = rpc.patch_list({'msgid': msgid})
        except ssl.SSLCertVerificationError:
            errprint('Error: server "%s" gave an SSL error, skipping' % url)
            continue
        except socket.gaierror as e:
            errprint('Error: server "%s" gave socket error "%s", skipping' % (url, e))
        if res:
            patch_id = res[0]['id']
            break
    else:
        errprint('Error: could not find patch based on message id')
        sys.exit(1)

    return _pick_patchwork(url, patch_id, args)

def _upstream(commit, urls, args):
    if args['debug']:
        print('_upstream: commit=%s' % commit)

    # Confirm an upstream remote is setup.
    remote = _find_upstream_remote(urls)
    if not remote:
        errprint('Error: need a valid upstream remote')
        sys.exit(1)

    branches = ['main', 'master']
    for branch in branches:
        remote_ref = '%s/%s' % (remote, branch)
        try:
            _git(['merge-base', '--is-ancestor', commit, remote_ref],
                 no_stderr=True)
        except subprocess.CalledProcessError:
            continue
        break
    else:
        errprint('Error: Commit not in %s, branches: %s' % (
                 remote, ', '.join(branches)))
        sys.exit(1)

    if args['source_line'] is None:
        commit = _git(['rev-parse', commit])
        args['source_line'] = ('(cherry picked from commit %s)' %
                               (commit))
    if args['tag'] is None:
        args['tag'] = 'UPSTREAM: '

    if args['replace']:
        _git(['reset', '--hard', 'HEAD~1'])

    return _git_returncode(['cherry-pick', commit])

def _match_upstream(match, args):
    """Match location: linux://HASH and upstream://HASH."""
    commit = match.group(1)
    return _upstream(commit, urls=UPSTREAM_URLS, args=args)

def _match_fromgit(match, args):
    """Match location: git://remote/branch/HASH."""
    remote = match.group(2)
    branch = match.group(3)
    commit = match.group(4)

    if args['debug']:
        print('_match_fromgit: remote=%s branch=%s commit=%s' %
              (remote, branch, commit))

    try:
        _git(['merge-base', '--is-ancestor', commit,
              '%s/%s' % (remote, branch)])
    except subprocess.CalledProcessError:
        errprint('Error: Commit not in %s/%s' % (remote, branch))
        sys.exit(1)

    url = _git(['remote', 'get-url', remote])

    if args['source_line'] is None:
        commit = _git(['rev-parse', commit])
        args['source_line'] = (
            '(cherry picked from commit %s\n %s %s)' % (commit, url, branch))
    if args['tag'] is None:
        args['tag'] = 'FROMGIT: '

    if args['replace']:
        _git(['reset', '--hard', 'HEAD~1'])

    return _git_returncode(['cherry-pick', commit])

def _match_gitfetch(match, args):
    """Match location: (git|https)://repoURL#branch/HASH."""
    remote = match.group(1)
    branch = match.group(3)
    commit = match.group(4)

    if args['debug']:
        print('_match_gitfetch: remote=%s branch=%s commit=%s' %
              (remote, branch, commit))

    try:
        _git(['fetch', remote, branch])
    except subprocess.CalledProcessError:
        errprint('Error: Branch not in %s' % remote)
        sys.exit(1)

    url = remote

    if args['source_line'] is None:
        commit = _git(['rev-parse', commit])
        args['source_line'] = (
            '(cherry picked from commit %s\n %s %s)' % (commit, url, branch))
    if args['tag'] is None:
        args['tag'] = 'FROMGIT: '

    if args['replace']:
        _git(['reset', '--hard', 'HEAD~1'])

    return _git_returncode(['cherry-pick', commit])

def _match_gitweb(match, args):
    """Match location: https://repoURL/commit/?h=branch&id=HASH."""
    remote = match.group(1)
    branch = match.group(2)
    commit = match.group(3)

    if args['debug']:
        print('_match_gitweb: remote=%s branch=%s commit=%s' %
              (remote, branch, commit))

    try:
        _git(['fetch', remote, branch])
    except subprocess.CalledProcessError:
        errprint('Error: Branch not in %s' % remote)
        sys.exit(1)

    url = remote

    if args['source_line'] is None:
        commit = _git(['rev-parse', commit])
        args['source_line'] = (
            '(cherry picked from commit %s\n %s %s)' % (commit, url, branch))
    if args['tag'] is None:
        args['tag'] = 'FROMGIT: '

    if args['replace']:
        _git(['reset', '--hard', 'HEAD~1'])

    return _git_returncode(['cherry-pick', commit])

def _remove_dup_bugs(bugs):
    """Remove the duplicated bugs from a string keeping the original order."""

    # Standardize all the spacing around bugs
    bugs = re.sub(r'\s*,\s*', ', ', bugs)

    # Create a list of bugs
    bugs = bugs.split(', ')

    # Remove duplicates keeping order
    bugs = list(OrderedDict.fromkeys(bugs).keys())

    # Convert into a string again
    bugs = ', '.join(bugs)

    return bugs

def main(args):
    """This is the main entrypoint for fromupstream.

    Args:
        args: sys.argv[1:]

    Returns:
        An int return code.
    """
    parser = argparse.ArgumentParser()

    parser.add_argument('--bug', '-b', action='append', default=[],
                        type=str, help='BUG= line')
    parser.add_argument('--test', '-t', action='append', default=[],
                        type=str, help='TEST= line')
    parser.add_argument('--crbug', action='append', default=[],
                        type=int, help='BUG=chromium: line')
    parser.add_argument('--buganizer', action='append', default=[],
                        type=int, help='BUG=b: line')
    parser.add_argument('--changeid', '-c',
                        help='Overrides the gerrit generated Change-Id line')
    parser.add_argument('--cqdepend',
                        type=str, help='Cq-Depend: line')

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
                        'Message-ID (msgid://MSGID), '
                        'linux commit like linux://HASH, '
                        'upstream commit like upstream://HASH, or '
                        'git reference like git://remote/branch/HASH or '
                        'git://repoURL#branch/HASH or '
                        'https://repoURL#branch/HASH or '
                        'https://repoURL/commit/?h=branch&id=HASH')

    args = vars(parser.parse_args(args))

    cq_depends = [args['cqdepend']] if args['cqdepend'] else []

    bugs = args['bug']
    bugs += ['b:%d' % x for x in args['buganizer']]
    bugs += ['chromium:%d' % x for x in args['crbug']]
    bugs = ', '.join(bugs)
    bugs = _remove_dup_bugs(bugs)
    bug_lines = [x.strip(' ,') for x in
                 _wrap_commit_line('BUG=', bugs).split('\n')]

    test_lines = [_wrap_commit_line('TEST=', x) for x in args['test']]

    if args['replace']:
        old_commit_message = _git(['show', '-s', '--format=%B', 'HEAD'])

        # It is possible that multiple Change-Ids are in the commit message
        # (due to cherry picking).  We only want to pull out the first one.
        changeid_match = re.search('^Change-Id: (.*)$',
                                   old_commit_message, re.MULTILINE)
        if args['changeid'] is None and changeid_match:
            args['changeid'] = changeid_match.group(1)

        if not cq_depends:
            cq_depends = re.findall(r'^Cq-Depend:\s+(.*)$',
                                    old_commit_message, re.MULTILINE)

        if not bug_lines:
            bug_lines = re.findall(r'^BUG=(.*)$',
                                   old_commit_message, re.MULTILINE)

        if not test_lines:
            # Note: use (?=...) to avoid to consume the source string
            test_lines = re.findall(r"""
                ^TEST=(.*?)     # Match start from TEST= until
                \n              # (to remove the tailing newlines)
                (?=^$|          # a blank line
                   ^Cq-Depend:| # or Cq-Depend:
                   ^Change-Id:| # or Change-Id:
                   ^BUG=|       # or following BUG=
                   ^TEST=)      # or another TEST=
                """,
                old_commit_message, re.MULTILINE | re.DOTALL | re.VERBOSE)

    if not bug_lines or not test_lines:
        parser.error('BUG=/TEST= lines are required; --replace can help '
                     'automate, or set via --bug/--test')

    if args['debug']:
        pprint.pprint(args)

    re_matches = (
        (re.compile(r'^pw://(([^/]+)/)?(.+)'), _match_patchwork),
        (re.compile(r'^msgid://<?([^>]*)>?'), _match_msgid),
        (re.compile(r'^linux://([0-9a-f]+)'), _match_upstream),
        (re.compile(r'^upstream://([0-9a-f]+)'), _match_upstream),
        (re.compile(r'^(from)?git://([^/\#]+)/([^#]+)/([0-9a-f]+)$'),
         _match_fromgit),
        (re.compile(r'^((git|https)://.+)#(.+)/([0-9a-f]+)$'), _match_gitfetch),
        (re.compile(r'^(https://.+)/commit/\?h=(.+)\&id=([0-9a-f]+)$'), _match_gitweb),
    )

    # Backup user provided parameters
    user_source_line = args['source_line']
    user_tag = args['tag']
    user_changeid = args['changeid']

    for location in args['locations']:
        # Restore user parameters
        args['source_line'] = user_source_line
        args['tag'] = user_tag
        args['changeid'] = user_changeid

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
        commit_message = _git(['show', '-s', '--format=%B', 'HEAD'])

        # Remove stray Change-Id, most likely from merge resolution
        commit_message = re.sub(r'Change-Id:.*\n?', '', commit_message)

        # Note the source location before tagging anything else
        commit_message += '\n' + args['source_line']

        # add automatic Change ID, BUG, and TEST (and maybe signoff too) so
        # next commands know where to work on
        commit_message += '\n'
        commit_message += conflicts
        commit_message += '\n'
        commit_message += '\n'.join('BUG=%s' % bug for bug in bug_lines)
        commit_message += '\n'
        commit_message += '\n'.join('TEST=%s' % t for t in test_lines)

        extra = []
        if args['signoff']:
            signoff = 'Signed-off-by: %s <%s>' % (
                    _git(['config', 'user.name']),
                    _git(['config', 'user.email']))
            if not signoff in commit_message.splitlines():
                extra += ['-s']
        _git(['commit'] + extra + ['--amend', '-F', '-'], stdin=commit_message)

        # re-extract commit message
        commit_message = _git(['show', '-s', '--format=%B', 'HEAD'])

        # If we see a "Link: " that seems to point to a Message-Id with an
        # automatic Change-Id we'll snarf it out.
        mo = re.search(r'^Link:.*(I[a-f0-9]{40})@changeid', commit_message,
                       re.MULTILINE)
        if mo and args['changeid'] is None:
            args['changeid'] = mo.group(1)

        # replace changeid if needed
        if args['changeid'] is not None:
            commit_message = re.sub(r'(Change-Id: )(\w+)', r'\1%s' %
                                    args['changeid'], commit_message)
            args['changeid'] = None

        if cq_depends:
            commit_message = re.sub(
                r'(Change-Id: \w+)',
                r'%s\n\1' % '\n'.join('Cq-Depend: %s' % c for c in cq_depends),
                commit_message)

        # decorate it that it's from outside
        commit_message = args['tag'] + commit_message

        # commit everything
        _git(['commit', '--amend', '-F', '-'], stdin=commit_message)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
