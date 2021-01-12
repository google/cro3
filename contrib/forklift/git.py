# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides some helpers for interacting with git."""

import re
import subprocess

class Git:
    """A class which provides helpers for interacting with git."""
    def __init__(self, path='.'):
        self._cmd = ['git', '-C', path]

    def _run(self, cmd, stdin=None):
        """Runs a git command with the appropriate working dir.

        Args:
            cmd: The command to run (in array fmt, ie: ['log', '--oneline']).
            stdin: Optionally provide stdin input to the command.

        Returns:
            (returncode,stdout,stderr) from the command
        """
        run_cmd = self._cmd + cmd
        ret = subprocess.run(run_cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, input=stdin,
                             encoding='UTF-8')
        return (ret.returncode, ret.stdout, ret.stderr)

    @staticmethod
    def _generate_remote_name(remote):
        """Generates a remote name unique for the given url.

        The result is the remote url without the protocol and special
        characters. This allows us to resolve git://git.kernel.org and
        https://git.kernel.org as the same remote.

        Args:
            remote: The remote tree's URL (including protocol).

        Returns:
            The unique remote name.
        """
        name = re.sub(r'([a-z]*\://)|\W', '', remote, flags=re.I)
        return f'fl-{name}'

    def fetch_refspec_from_remote(self, remote, refspec):
        """Fetches the given refspec from the given remote.

        Args:
            remote: The remote tree's URL (including protocol).
            refspec: The remote refspec to fetch.

        Returns:
            True if the fetch was successful, False otherwise.
        """
        remote_name = Git._generate_remote_name(remote)
        # Ignore failures from remote add since the remote might already exist.
        self._run(['remote', 'add', remote_name, remote])
        ret, *_ = self._run(['fetch', remote_name, refspec])
        return ret == 0

    def get_commits_in_range(self, start, end, include_merges=False):
        """Get a list of commits between start and end.

        Args:
            start: The range's beginning refspec.
            end: The range's ending refspec.
            include_merges: Should the results include merge commits?

        Returns:
            True if successful, False otherwise.
        """
        cmd = ['log', '--format=%H']
        if not include_merges:
            cmd += ['--no-merges']
        ret, commits, _ = self._run(cmd + [f'{start}..{end}'])
        if ret != 0:
            return None

        return commits.splitlines()

    def commit_in_local_branch(self, commit, common_ancestor=None,
                               include_cherry_picks=False):
        """Look for the given commit in the local branch.

        Args:
            commit: The commit to look for.
            common_ancestor: The common ancestor between local and upstream.
            include_cherry_picks: Search cherry-picked commits as well.

        Returns:
            True if the commit is found in the local branch, False otherwise.
        """
        ret, *_ = self._run(['merge-base', '--is-ancestor', commit, 'HEAD'])
        if ret == 0:
            return True

        if not include_cherry_picks:
            return False

        # Get the affected files to narrow down the grep below
        ret, files, _ = self._run(['diff-tree', '--no-commit-id', '--name-only',
                                   '-r', commit])
        if ret != 0:
            return False

        # Inspect the last 10 commits to each file and pick the file which has
        # the oldest for the grep below. This will hopefully more often than
        # not choose the least active file (ie: smallest history) to speed up
        # the grep below. We could of course just count all the commits, but
        # that would take a long time and probably [hand waving] take more time
        # overall than grepping a random file from the commit.
        lru = ('', -1)
        for f in files.splitlines():
            ret, changes, _ = self._run(['log', '-10', '--format=%ct', commit,
                                         '--', f])
            if ret != 0 or not changes:
                continue

            oldest = changes.splitlines()[-1]
            if lru[1] == -1 or oldest < lru[1]:
                lru = (f, oldest)

        cmd = ['log', '--extended-regexp', '--grep',
               f'(cherry.picked from( commit)? {commit})']
        if common_ancestor:
            cmd += [f'{common_ancestor}..']
        if lru[1] != -1:
            cmd += ['--', lru[0]]
        ret, commits, _ = self._run(cmd)
        if ret == 0 and commits:
            return True

        return False
