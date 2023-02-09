# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides some helpers for interacting with git."""

import re
import subprocess


class Git:
    """A class which provides helpers for interacting with git."""

    def __init__(self, path="."):
        self._cmd = ["git", "-C", path]

    def _run(self, cmd, stdin=None):
        """Runs a git command with the appropriate working dir.

        Args:
            cmd: The command to run (in array fmt, ie: ['log', '--oneline']).
            stdin: Optionally provide stdin input to the command.

        Returns:
            (returncode,stdout,stderr) from the command
        """
        run_cmd = self._cmd + cmd
        ret = subprocess.run(
            run_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            input=stdin,
            encoding="UTF-8",
        )
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
        name = re.sub(r"([a-z]*\://)|\W", "", remote, flags=re.I)
        return f"fl-{name}"

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
        self._run(["remote", "add", remote_name, remote])
        ret, *_ = self._run(["fetch", remote_name, refspec])
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
        cmd = ["log", "--format=%H"]
        if not include_merges:
            cmd += ["--no-merges"]
        ret, commits, _ = self._run(cmd + [f"{start}..{end}"])
        if ret != 0:
            return None

        return commits.splitlines()

    def commit_in_local_branch(
        self, commit, common_ancestor=None, include_cherry_picks=False
    ):
        """Look for the given commit in the local branch.

        Args:
            commit: The commit to look for.
            common_ancestor: The common ancestor between local and upstream.
            include_cherry_picks: Search cherry-picked commits as well.

        Returns:
            True if the commit is found in the local branch, False otherwise.
        """
        ret, *_ = self._run(["merge-base", "--is-ancestor", commit, "HEAD"])
        if ret == 0:
            return True

        if not include_cherry_picks:
            return False

        # Get the affected files to narrow down the grep below
        ret, files, _ = self._run(
            ["diff-tree", "--no-commit-id", "--name-only", "-r", commit]
        )
        if ret != 0:
            return False

        # Inspect the last 10 commits to each file and pick the file which has
        # the oldest for the grep below. This will hopefully more often than
        # not choose the least active file (ie: smallest history) to speed up
        # the grep below. We could of course just count all the commits, but
        # that would take a long time and probably [hand waving] take more time
        # overall than grepping a random file from the commit.
        lru = ("", -1)
        for f in files.splitlines():
            ret, changes, _ = self._run(
                ["log", "-10", "--format=%ct", commit, "--", f]
            )
            if ret != 0 or not changes:
                continue

            oldest = changes.splitlines()[-1]
            if lru[1] == -1 or oldest < lru[1]:
                lru = (f, oldest)

        cmd = [
            "log",
            "--extended-regexp",
            "--grep",
            f"(cherry.picked from( commit)? {commit})",
        ]
        if common_ancestor:
            cmd += [f"{common_ancestor}.."]
        if lru[1] != -1:
            cmd += ["--", lru[0]]
        ret, commits, _ = self._run(cmd)
        if ret == 0 and commits:
            return True

        return False

    def cherry_pick(self, commit, skip_empty=False):
        """Cherry picks a commit into the local branch.

        Args:
            commit: The hash of the commit to be cherry-picked.
            skip_empty: Detect if the cherry-pick is empty and skip it.

        Returns:
            (ret, skipped) ret will be True on success, skipped will be True if
            the patch is skipped.
        """
        ret, _, err = self._run(["cherry-pick", "-s", "-x", commit])
        if ret == 0:
            return (True, False)

        if not skip_empty:
            return (False, False)

        if "The previous cherry-pick is now empty" not in err:
            return (False, False)

        # Double check we don't have any local changes
        ret, files, _ = self._run(["status", "-s", "-uno"])
        if ret != 0 or files != "":
            return (False, False)

        ret, *_ = self._run(["cherry-pick", "--skip"])
        return (ret == 0, ret == 0)

    def get_conflicting_files(self):
        """Returns a list of conflicting files in the local git tree.

        Returns:
            A list of files with conflicts.
        """
        ret, files, _ = self._run(["status", "-s"])
        if ret != 0:
            return []

        conflicts = []
        for f in files.splitlines():
            if not f.startswith("UU"):
                continue
            conflicts.append(f.split(" ")[1])

        return conflicts

    def get_commit_message(self, commit="HEAD"):
        """Returns the commit message for the given commit.

        Args:
            commit: The hash of the commit to be shown

        Returns:
            (ret, message) ret will be True on success, message will have the
            commit message.
        """
        ret, message, _ = self._run(["show", "--quiet", "--format=%B", commit])
        return (ret == 0, message)

    def set_commit_message(self, message):
        """Amends the commit at HEAD with the given commit message.

        Args:
            message: Message to use for the commit at HEAD.

        Returns:
            True if successful, False otherwise.
        """
        ret, *_ = self._run(["commit", "--amend", "-F", "-"], stdin=message)
        return (ret == 0, message)

    def generate_change_id(self, commit="HEAD"):
        """Generates the Change-Id value for the commit at HEAD

        Args:
            commit: The hash of the commit to generate the Change-Id for.

        Returns:
            (ret, change_id) ret will be True on success, change_id is the
            Change-Id for the commit at HEAD.
        """
        obj = ""

        ret, stdout, _ = self._run(["write-tree"])
        if ret == 0 and stdout:
            obj += f"tree {stdout}"

        ret, stdout, _ = self._run(["rev-parse", f"{commit}^0"])
        if ret == 0 and stdout:
            obj += f"parent {stdout}"

        ret, stdout, _ = self._run(["var", "GIT_AUTHOR_IDENT"])
        if ret == 0 and stdout:
            obj += f"author {stdout}"

        ret, stdout, _ = self._run(["var", "GIT_COMMITTER_IDENT"])
        if ret == 0 and stdout:
            obj += f"committer {stdout}"

        ret, commit_msg = self.get_commit_message(commit)
        if ret:
            obj += f"\n{commit_msg}"

        ret, stdout, _ = self._run(
            ["hash-object", "-t", "commit", "--stdin"], stdin=obj
        )
        return (ret == 0, f"I{stdout.strip()}")

    def show(self, commit):
        """Returns the 'git show' output for the given commit.

        Args:
            commit: The commit to show.

        Returns:
            A string with the 'git show' output.
        """
        _, output, _ = self._run(["show", commit])
        return output

    def commit_diff(self, commit, path):
        """Returns the changes to a given file in the given commit.

        Args:
            commit: The commit to return the diff for.
            path: The file path to limit the diff with.

        Returns:
            The diff introduced in commit.
        """
        ret, output, _ = self._run(["diff-tree", "-p", commit, "--", path])
        if ret != 0:
            return ""

        # Split out the header goop in the first 5 lines
        return "\n".join(output.splitlines()[5:])

    def blame(self, path, refspec=None):
        """Returns the 'git blame' output for the given path at refspec.

        Args:
            path: The path of the file being blamed.
            refspec: The git refspec to inspect the file at.

        Returns:
            A string with the 'git blame' output.
        """
        cmd = ["blame"]
        if refspec:
            cmd += [refspec]
        cmd += ["--", path]
        _, output, _ = self._run(cmd)
        return output
