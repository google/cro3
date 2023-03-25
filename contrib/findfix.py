#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Report branches including the provided fix(es)
"""

import argparse
import re
import subprocess
import sys


STABLE_URLS = [
    'git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git',
]

UPSTREAM_URLS = [
    'git://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
    'https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git',
    'https://kernel.googlesource.com/pub/scm/linux/kernel/git/torvalds/linux.git',
]

STABLE_QUEUE_URLS = [
    'git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable-rc.git'
]

CHROMEOS_URLS = [
    'https://chromium.googlesource.com/chromiumos/third_party/kernel'
]

BRANCHES = ('6.1', '5.15', '5.10', '5.4', '4.19', '4.14')

CHROMEOS_RELEASE_BRANCHES = ('R102-14695.B', 'R108-15183.B', 'R111-15329.B',
                             'R112-15359.B', 'R113-15393.B')

def _git(args, stdin=None, encoding='utf-8'):
    """Calls a git subcommand.

    Similar to subprocess.check_output.

    Args:
        args: subcommand + args passed to 'git'.
        stdin: a string or bytes (depending on encoding) that will be passed
            to the git subcommand.
        encoding: either 'utf-8' (default) or None. Override it to None if
            you want both stdin and stdout to be raw bytes.

    Returns:
        the stdout of the git subcommand, same type as stdin. The output is
        also run through strip to make sure there's no extra whitespace.

    Raises:
        subprocess.CalledProcessError: when return code is not zero.
            The exception has a .returncode attribute.
    """

    try:
        # print(['git'] + args)
        return subprocess.run(
            ['git'] + args,
            encoding=encoding,
            input=stdin,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=True,
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return None


def _find_remote(urls):
    """Find a remote pointing to a given repository."""

    # https remotes may end with or without '/'. Cover both variants.
    _urls = []
    for url in urls:
        _urls.append(url)
        if url.startswith('https://'):
            if url.endswith('/'):
                _urls.append(url.rstrip('/'))
            else:
                _urls.append(url + '/')

    for remote in _git(['remote']).splitlines():
        try:
            if _git(['remote', 'get-url', remote]) in _urls:
                return remote
        except subprocess.CalledProcessError:
            # Kinda weird, get-url failing on an item that git just gave us.
            continue
    return None


def integrated(sha):
    """Find tag at which a given SHA was integrated"""
    fixed = _git(['describe', '--match', 'v*', '--contains', sha])
    if fixed:
        fixed = fixed.split('~')[0]
    else:
        # This patch may not be upstream.
        upstream = _find_remote(UPSTREAM_URLS)
        gitcommand = ['merge-base', '--is-ancestor', sha, f'{upstream}/master']
        if _git(gitcommand) is not None:
            fixed = "ToT"
        else:
            fixed = None

    return fixed


def compare_releases(r1, r2):
    """Compare two releases.

    Return 0 if equal, <0 if r1 is older than r2, >0 if r1 is newer than r2
    """

    s1 = 0
    s2 = 0

    if r1 == r2:
        return 0
    if r1 == 'ToT':
        return 1
    if r2 == 'ToT':
        return -1

    m = re.match(r'(?:v)(\d+).(\d+)(?:\.(\d+))?.*', r1)
    if m:
        s1 = int(m.group(1)) * 1000000
        s1 += int(m.group(2)) * 1000
        if m.group(3) is not None:
            s1 += int(m.group(3))

    m = re.match(r'(?:v)?(\d+).(\d+)(?:\.(\d+))?.*', r2)
    if m:
        s2 = int(m.group(1)) * 1000000
        s2 += int(m.group(2)) * 1000
        if m.group(3) is not None:
            s2 += int(m.group(3))

    if s1 == s2:
        return 0
    if s1 < s2:
        return -1
    return 1


def checkbranch(remote, baseline, subject, queued=False):
    """Check if a commit is present in a branch.

    Check if a commit described by its subject line is present
    in the provided remote and branch (identified by its baseline version
    number)
    """

    found=False

    gitcommand = ['log', '--oneline', f'v{baseline}..{remote}/linux-{baseline}.y']
    commits = _git(gitcommand)

    if commits: # pylint: disable=too-many-nested-blocks
        for commit in commits.splitlines():
            if subject in commit:
                ssha = commit.split(' ')[0]
                isha = integrated(ssha)
                if not isha or isha == 'ToT':
                    if queued:
                        print((f'  Expected to be fixed in chromeos-{baseline} '
                               f'with next stable release merge (sha {ssha})'))
                elif not queued:
                    msg=f'  Fixed in chromeos-{baseline} with merge of {isha} (sha {ssha})'
                    print(msg)
                    # Now check release branches
                    # FIXME: Patches may be in release branches but use a different SHA there.
                    # Output in that case should be "Fixed in <Release> (sha <sha>)"
                    chromeos_remote = _find_remote(CHROMEOS_URLS)
                    if chromeos_remote:
                        contained = []
                        not_contained = []
                        for b in CHROMEOS_RELEASE_BRANCHES:
                            release_branch = f'release-{b}-chromeos-{baseline}'
                            release = b.split('-', maxsplit=1)[0]
                            gitcommand = ['merge-base', '--is-ancestor', ssha,
                                          f'{chromeos_remote}/{release_branch}']
                            result = _git(gitcommand)
                            if result is None:
                                not_contained += [release]
                            else:
                                contained += [release]
                        if not_contained:
                            print('    Not in ' + ', '.join(not_contained))
                        if contained:
                            print('    In ' + ', '.join(contained))
                found=True
                break

    return found


def main(args):
    """Main entrypoint.

    Args:
        args: sys.argv[1:]

    Returns:
        An int return code.
    """

    parser = argparse.ArgumentParser()

    parser.add_argument('shas', nargs='+',
                        help='A valid SHA')

    args = vars(parser.parse_args(args))

    remote = _find_remote(STABLE_URLS)
    if remote:
        _git(['fetch', remote])
    else:
        print('Stable remote not found, results may be incomplete')

    queue_remote = _find_remote(STABLE_QUEUE_URLS)
    if queue_remote:
        _git(['fetch', queue_remote])
    else:
        print('Stable queue remote not found, results may be incomplete')

    chromeos_remote = _find_remote(CHROMEOS_URLS)
    if chromeos_remote:
        _git(['fetch', chromeos_remote])
    else:
        print('ChromeOS remote not found, results may be incomplete')

    # Try to find and fetch upstream
    upstream = _find_remote(UPSTREAM_URLS)
    if upstream:
        _git(['fetch', upstream])

    for sha in args['shas']:
        subject = _git(['show', '--pretty=format:%s', '-s', sha])
        if not subject:
            print(f'Subject not found for SHA {sha}')
            sys.exit(1)

        full_sha = _git(['show', '--pretty=format:%H', '-s', sha])
        if not full_sha:
            print(f'Failed to extract full SHA for SHA {sha}')
            sys.exit(1)

        ssha = full_sha[0:11]

        integrated_branch = integrated(ssha)
        if integrated_branch:
            print(f'Upstream commit {ssha} ("{subject}")')
            print(f'  Integrated in {integrated_branch}')
        else:
            # If the patch is not upstream, do not bother trying to find
            # ChromeOS branches.
            # FIXME: We should try to find non-upstream patches as well.
            print(f'Commit {ssha} ("{subject}")')
            print('  Not found in upstream kernel')
            continue

        for branch in BRANCHES:
            if compare_releases(integrated_branch, branch) > 0:
                if (not checkbranch(remote, branch, subject) and
                    (not queue_remote
                     or not checkbranch(queue_remote, branch, subject, queued=True))):
                    print(f'  Not in chromeos-{branch}')


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
