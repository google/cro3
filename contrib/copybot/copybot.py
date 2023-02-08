#!/usr/bin/env python3
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""CopyBot script.

This script copies commits from one repo (the "upstream") to another
(the "downstream").

Usage: copybot.py [options...] upstream_repo:branch downstream_repo:branch
"""

import argparse
import contextlib
import enum
import json
import logging
import os
import pathlib
import re
import shlex
import subprocess
import tempfile
import time

import requests  # pylint: disable=import-error


logger = logging.getLogger(__name__)

# Matches a full 40-character commit hash.
_COMMIT_HASH_PATTERN = re.compile(r"\b[0-9a-f]{40}\b")


class MergeConflictBehavior(enum.Enum):
    """How to behave on merge conflicts.

    FAIL: Stop immediately. Don't upload anything.
    SKIP: Skip the commit that failed to merge. Summarize the failed
        commits at the end of the execution, and exit failure status.
    """

    FAIL = enum.auto()
    SKIP = enum.auto()


class MergeConflictError(Exception):
    """A commit cannot be cherry-picked due to a conflict."""


class EmptyCommitError(Exception):
    """A commit cannot be cherry-picked as it results in an empty commit."""


class CopybotFatalError(Exception):
    """Copybot fatal error."""

    enum_name = "FAILURE_UNKNOWN"

    def __init__(self, *args, commits=(), **kwargs):
        self.commits = commits
        super().__init__(*args, **kwargs)


class UpstreamFetchError(CopybotFatalError):
    """Copybot died as the upstream failed to fetch."""

    enum_name = "FAILURE_UPSTREAM_FETCH_ERROR"


class DownstreamFetchError(CopybotFatalError):
    """Copybot died as the downstream failed to fetch."""

    enum_name = "FAILURE_DOWNSTREAM_FETCH_ERROR"


class PushError(CopybotFatalError):
    """Copybot died as it failed to push to the downstream GoB host."""

    enum_name = "FAILURE_DOWNSTREAM_PUSH_ERROR"


class MergeConflictsError(CopybotFatalError):
    """Copybot ran, but encountered merge conflicts."""

    enum_name = "FAILURE_MERGE_CONFLICTS"


class GitRepo:
    """Class wrapping common Git repository actions."""

    def __init__(self, git_dir):
        self.git_dir = git_dir

    def _run_git(self, *args, **kwargs):
        """Wrapper to run git with the provided arguments."""
        argv = ["git", "-C", self.git_dir, "--no-pager", *args]
        logger.info("Run `%s`", " ".join(shlex.quote(str(arg)) for arg in argv))
        kwargs.setdefault("encoding", "utf-8")
        kwargs.setdefault("errors", "replace")
        try:
            return subprocess.run(
                argv,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                **kwargs,
            )
        except subprocess.CalledProcessError as e:
            logger.error("Git command failed!")
            logger.error("  STDOUT:")
            for line in e.stdout.splitlines():
                logger.error("    %s", line)
            logger.error("  STDERR:")
            for line in e.stderr.splitlines():
                logger.error("    %s", line)
            raise

    @classmethod
    def init(cls, git_dir):
        """Do a `git init` to create a new repository."""
        repo = cls(git_dir)
        repo._run_git("init")  # pylint: disable=protected-access
        return repo

    def rev_parse(self, rev="HEAD"):
        """Do a `git rev-parse`."""
        result = self._run_git("rev-parse", rev)
        return result.stdout.rstrip()

    def fetch(self, remote, ref=None):
        """Do a `git fetch`.

        Returns:
            The full commit hash corresponding to FETCH_HEAD.
        """
        extra_args = []
        if ref:
            extra_args.append(ref)
        self._run_git("fetch", remote, *extra_args)
        return self.rev_parse("FETCH_HEAD")

    def checkout(self, ref):
        """Do a `git checkout`."""
        return self._run_git("checkout", ref)

    def log(self, revision_range="HEAD", fmt=None, num=0):
        """Do a `git log`."""
        extra_args = []
        if fmt:
            extra_args.append(f"--format={fmt}")
        if num:
            extra_args.append(f"-n{num}")
        return self._run_git("log", revision_range, *extra_args)

    def log_hashes(self, revision_range="HEAD", num=0):
        """Get the commit log as a list of commit hashes."""
        result = self.log(revision_range=revision_range, fmt="%H", num=num)
        return result.stdout.splitlines()

    def get_commit_message(self, rev="HEAD"):
        """Get a commit message of a commit."""
        result = self.log(revision_range=rev, num=1, fmt="%B")
        return result.stdout

    def commit_file_list(self, rev="HEAD"):
        """Get the files modified by a commit."""
        result = self._run_git("show", "--pretty=", "--name-only", rev)
        return result.stdout.splitlines()

    def show(self, rev="HEAD", files=()):
        """Do a `git show`."""
        result = self._run_git("show", rev, "--", *files)
        return result.stdout

    def apply(self, patch):
        """Apply a patch to the staging area."""
        return self._run_git("apply", "--cached", "-", input=patch)

    def commit(self, message, amend=False, sign_off=False):
        """Create a commit.

        Returns:
            The commit hash.
        """
        extra_args = []
        if amend:
            extra_args.append("--amend")
        if sign_off:
            extra_args.append("--signoff")
        self._run_git("commit", "-m", message, *extra_args)
        return self.rev_parse()

    def reword(self, new_message, sign_off=False):
        """Reword the commit at HEAD.

        Returns:
            The new commit hash.
        """
        return self.commit(new_message, amend=True, sign_off=sign_off)

    @contextlib.contextmanager
    def temp_worktree(self, rev="HEAD"):
        """Context manager to create and destroy a temporary worktree."""
        # pylint: disable=consider-using-with
        tmpdir = tempfile.TemporaryDirectory()
        try:
            worktree_dir = pathlib.Path(tmpdir.name)
            self._run_git("worktree", "add", "-d", worktree_dir, rev)
            try:
                yield self.__class__(worktree_dir)
            finally:
                self._run_git("worktree", "remove", "--force", worktree_dir)
        finally:
            # We use a try/finally to cleanup the temporary directory
            # instead of a context manager as, in the successful
            # condition, the worktree directory will no longer exist
            # (git will have removed it).  In Python 3.10+, one can
            # use ignore_cleanup_errors=True, but the chroot is on
            # Python 3.6 right now.
            try:
                tmpdir.cleanup()
            except FileNotFoundError:
                pass

    def filter_commit(self, rev="HEAD", files=()):
        """Filter a commit to just certain files.

        Returns:
            The new commit hash.
        """
        old_message = self.get_commit_message(rev)
        patch = self.show(rev, files)

        with self.temp_worktree(f"{rev}~1") as worktree:
            worktree.apply(patch)
            return worktree.commit(old_message)

    def cherry_pick(self, rev):
        """Do a `git cherry-pick`.

        This will first try without any merge options, and if that fails,
        try again with -Xpatience, which is slower, but may be more likely
        to resolve a merge conflict.

        Raises:
            EmptyCommitError: The resultant commit was empty and should be
                skipped.
            MergeConflictError: There was a merge conflict that could not
                be resolved automatically with -Xpatience.
        """

        def _try_cherry_pick(extra_flags):
            try:
                self._run_git("cherry-pick", "-x", rev, *extra_flags)
            except subprocess.CalledProcessError as e:
                self._run_git("cherry-pick", "--abort")
                if "The previous cherry-pick is now empty" in e.stderr:
                    raise EmptyCommitError() from e
                raise MergeConflictError() from e

        exn = None
        for flags in ([], ["-Xpatience"]):
            try:
                _try_cherry_pick(flags)
            except MergeConflictError as e:
                exn = e
                continue
            else:
                return

        raise exn

    def push(self, url, refspec, options=()):
        """Do a `git push`."""
        args = []

        for option in options:
            args.extend(["-o", option])

        args.append(url)
        args.append(refspec)
        self._run_git("push", *args)


class Pseudoheaders:
    """Dictionary-like object for the pseudoheaders from a commit message.

    The pseudoheaders are the header-like lines often found in the
    bottom of a commit message.  Header names are case-insensitive.

    Pseudoheaders are parsed the same way that the "git footers"
    command parses them.
    """

    # Matches lines that look like a "header" (the conventional footer
    # lines in a commit message).
    _PSEUDOHEADER_PATTERN = re.compile(r"^(?:[A-Za-z0-9]+-)*[A-Za-z0-9]+:\s+")

    def __init__(self, header_list=()):
        self._header_list = list(header_list)

    @classmethod
    def from_commit_message(cls, commit_message):
        """Parse pseudoheaders from a commit message.

        Returns:
            Two values, a Pseudoheaders dictionary, and the commit
            message without any pseudoheaders.
        """
        message_lines = commit_message.splitlines()
        rewritten_message = []

        header_list = []
        for i, line in enumerate(message_lines):
            if i == 0 or not cls._PSEUDOHEADER_PATTERN.match(line):
                rewritten_message.append(line)
            else:
                name, _, value = line.partition(":")
                header_list.append((name, value.strip()))

        return cls(header_list), "".join(
            f"{line}\n" for line in rewritten_message
        )

    def prefix(self, prefix="Original-", keep=()):
        """Prefix all header keys with a string.

        Args:
            prefix: The prefix to use.
            keep: Headers which should not be modified.

        Returns:
            A new Pseudoheaders dictionary.
        """
        new_header_list = []

        # Constructing a new pseudoheaders dictionary ensures we
        # consider the keep list to be case insensitive.
        keep_dict = self.__class__([(key, True) for key in keep])

        for key, value in self._header_list:
            if keep_dict.get(key):
                new_header_list.append((key, value))
            else:
                new_header_list.append((f"{prefix}{key}", value))
        return self.__class__(new_header_list)

    def __getitem__(self, item):
        """Get a header value by name."""
        for key, value in self._header_list:
            if key.lower() == item.lower():
                return value
        raise KeyError(item)

    def get(self, item, default=None):
        """Get a header value by name, or return a default value."""
        try:
            return self[item]
        except KeyError:
            return default

    def __setitem__(self, key, value):
        """Add a header."""
        self._header_list.append((key, value))

    def add_to_commit_message(self, commit_message):
        """Add our pseudoheaders to a commit message.

        Returns:
            The new commit message.
        """
        message_lines = commit_message.splitlines()

        if not message_lines:
            message_lines = ["NO COMMIT MESSAGE"]

        # Ensure exactly one blank line separating body and pseudoheaders.
        while not message_lines[-1].strip():
            message_lines.pop()

        message_lines.append("")

        for key, value in self._header_list:
            message_lines.append(f"{key}: {value}")
        return "".join(f"{line}\n" for line in message_lines)


class Gerrit:
    """Wrapper for actions on a Gerrit host."""

    def __init__(self, hostname):
        self.hostname = hostname

    def search(self, query):
        """Do a query on Gerrit."""
        url = f"https://{self.hostname}/changes/"
        params = [
            ("q", query),
            ("o", "CURRENT_REVISION"),
            ("o", "CURRENT_COMMIT"),
            ("o", "COMMIT_FOOTERS"),
        ]
        while True:
            r = requests.get(url, params=params)
            if r.ok:
                break
            if r.status_code == requests.codes.too_many:
                time.sleep(1)
                continue
            r.raise_for_status()
            assert False

        if r.text[:5] != ")]}'\n":
            logger.error("Bad response from Gerrit: %r", r.text)
            raise ValueError("Unexpected JSON payload from gerrit")

        result = json.loads(r.text[5:])
        return result

    def find_pending_changes(self, project, branch, topic):
        """Find pending changes previously opened by CopyBot on Gerrit.

        Returns:
            A dictionary mapping upstream commit hashes to their
            current Change-Id on Gerrit.
        """
        query = f"status:open project:{project} branch:{branch} topic:{topic}"
        query_result = self.search(query)
        change_ids = {}
        for cl in query_result:
            change_id = cl["change_id"]
            current_revision_hash = cl["current_revision"]
            current_revision_data = cl["revisions"][current_revision_hash]
            commit_message = current_revision_data["commit"]["message"]
            rev_id = get_origin_rev_id(commit_message)
            if rev_id:
                change_ids[rev_id] = change_id
        return change_ids

    def get_skiplist(self, project, branch):
        """Find changes with the copybot-skip hashtag.

        Returns:
            The set of upstream commit hashes that should be skipped.
        """
        query = f"project:{project} branch:{branch} hashtag:copybot-skip"
        query_result = self.search(query)
        skipped_hashes = set()
        for cl in query_result:
            current_revision_hash = cl["current_revision"]
            current_revision = cl["revisions"][current_revision_hash]
            commit_message = current_revision["commit"]["message"]
            for commit_hash in _COMMIT_HASH_PATTERN.finditer(commit_message):
                skipped_hashes.add(commit_hash.group(0))
        return skipped_hashes

    @staticmethod
    def generate_change_id():
        """Generate a Gerrit Change-Id."""
        return f"I{os.urandom(20).hex()}"


def get_origin_rev_id(commit_message):
    """Get the origin revision hash from a commit message.

    Returns:
        The revision hash if one was found, or None otherwise.
    """
    pseudoheaders, _ = Pseudoheaders.from_commit_message(commit_message)
    origin_revid = pseudoheaders.get("GitOrigin-RevId")
    if not origin_revid:
        origin_revid = pseudoheaders.get("Original-Commit-Id")
    return origin_revid


def find_last_merged_rev(repo, upstream_rev, downstream_rev):
    """Find the last merged revision in a Git repo.

    Args:
        repo: The GitRepo.
        upstream_rev: The commit hash of the upstream HEAD.
        downstream_rev: The commit hash of the downstream HEAD.

    Returns:
        A commit hash of the last merged revision by CopyBot, or the
        first common commit hash in both logs.

    Raises:
        ValueError: No common history could be found.
    """
    upstream_hashes = repo.log_hashes(upstream_rev)
    downstream_hashes = repo.log_hashes(downstream_rev)

    for rev in downstream_hashes:
        commit_message = repo.get_commit_message(rev)
        origin_revid = get_origin_rev_id(commit_message)
        if origin_revid:
            return origin_revid
        if rev in upstream_hashes:
            return rev

    raise ValueError(
        "Downstream has no GitOrigin-RevId commits, and upstream and "
        "downstream share no common history."
    )


def find_commits_to_copy(
    repo,
    upstream_rev,
    last_merged_rev,
    skip_revs=(),
    exclude_file_patterns=(),
):
    """Find the commits to copy to downstream.

    Args:
        repo: The GitRepo.
        upstream_rev: The commit hash of the upstream HEAD.
        last_merged_rev: The last upstream commit hash merged.
        skip_revs: Any upstream commit hashes that should be skipped.
        exclude_file_patterns: Regular expressions of file paths that
            should not be copied.

    Returns:
        Three values: a list of the commit hashes to copy, a
        dictionary mapping commit hashes to the files that should be
        included, and a dictionary mapping commit hashes to the files
        that should be skipped.

    Raises:
        ValueError: If the provided last merged commit hash does not
           exist in upstream commit history.
    """
    commits_to_copy = []
    commit_files_map = {}
    skipped_files_map = {}

    for rev in repo.log_hashes(upstream_rev):
        if rev == last_merged_rev:
            break

        if rev in skip_revs:
            logger.info("Skip %s due to copybot-skip hashtag", rev)
            continue

        commit_files = repo.commit_file_list(rev)
        filtered_commit_files = []
        for path in commit_files:
            if not any(p.fullmatch(path) for p in exclude_file_patterns):
                filtered_commit_files.append(path)

        if not filtered_commit_files:
            logger.info(
                "Skip commit %s due to empty file list after filtering "
                "(before filtering was %r)",
                rev,
                commit_files,
            )
            continue

        commit_files_map[rev] = filtered_commit_files
        skipped_files_map[rev] = [
            path for path in commit_files if path not in filtered_commit_files
        ]

        commits_to_copy.append(rev)
    else:
        raise ValueError(
            "Last merged revision cannot be found in upstream history"
        )

    return commits_to_copy, commit_files_map, skipped_files_map


def rewrite_commit_message(
    repo,
    upstream_rev,
    change_id,
    skipped_files=(),
    prepend_subject="",
    sign_off=False,
    keep_pseudoheaders=(),
):
    """Reword the commit at HEAD with appropriate metadata.

    Args:
        repo: The GitRepo to operate on.
        upstream_rev: The upstream commit hash corresponding to this commit.
        change_id: The Change-Id to add to the commit.
        skipped_files: The list of files skipped.
        prepend_subject: A string to prepend the subject line with.
        sign_off: True if Signed-off-by should be added to the commit message.
        keep_pseudoheaders: Pseudoheaders which should not be prefixed.
    """
    commit_message = repo.get_commit_message()
    if prepend_subject:
        commit_message = prepend_subject + commit_message
    pseudoheaders, commit_message = Pseudoheaders.from_commit_message(
        commit_message
    )
    pseudoheaders = pseudoheaders.prefix(keep=keep_pseudoheaders)

    for path in skipped_files:
        pseudoheaders["CopyBot-Skipped-File"] = path

    pseudoheaders["GitOrigin-RevId"] = upstream_rev
    pseudoheaders["Change-Id"] = change_id

    commit_message = pseudoheaders.add_to_commit_message(commit_message)
    repo.reword(commit_message, sign_off=sign_off)


def get_push_refspec(args, downstream_branch):
    """Generate a push refspec for Gerrit.

    Args:
        args: The parsed command line arguments.
        downstream_branch: The branch to push to.

    Returns:
        A push refspec as a string.
    """
    push_options = []

    def _add_push_option(key, value):
        for option in value.split(","):
            push_options.append(f"{key}={option}")

    _add_push_option("topic", args.topic)

    for label in args.labels:
        _add_push_option("l", label)

    for cc in args.ccs:
        _add_push_option("cc", cc)

    for reviewer in args.reviewers:
        _add_push_option("r", reviewer)

    for hashtag in args.hashtags:
        _add_push_option("ht", hashtag)

    return f"HEAD:refs/for/{downstream_branch}%{','.join(push_options)}"


def run_copybot(args, tmp_dir):
    """Run copybot.

    Args:
        args: The parsed command line arguments.
        tmp_dir: A temporary directory to use for Git operations.
    """
    upstream_url, sep, upstream_branch = args.upstream.rpartition(":")
    if not sep:
        upstream_branch = "main"
    downstream_url, sep, downstream_branch = args.downstream.rpartition(":")
    if not sep:
        downstream_branch = upstream_branch

    exclude_file_patterns = [
        re.compile(pattern) for pattern in args.exclude_file_patterns
    ]
    merge_conflict_behavior = MergeConflictBehavior[
        args.merge_conflict_behavior
    ]

    m = re.fullmatch(
        r"https://(chromium|chrome-internal)(?:-review)?\.googlesource\.com/(.*)",
        downstream_url,
    )
    if not m:
        # TODO(jrosenth): Support non-GoB Gerrit in the future?
        raise CopybotFatalError("Non-GoB downstream is currently not supported")

    downstream_gob_host = m.group(1)
    downstream_project = m.group(2)

    gerrit = Gerrit(f"{downstream_gob_host}-review.googlesource.com")
    pending_changes = gerrit.find_pending_changes(
        downstream_project,
        downstream_branch,
        args.topic,
    )
    logger.info(
        "Found %s pending changes already on Gerrit", len(pending_changes)
    )

    repo = GitRepo.init(tmp_dir)
    try:
        upstream_rev = repo.fetch(upstream_url, upstream_branch)
    except subprocess.CalledProcessError as e:
        raise UpstreamFetchError(
            f"Failed to fetch branch {upstream_branch} from {upstream_url}"
        ) from e

    try:
        downstream_rev = repo.fetch(downstream_url, downstream_branch)
    except subprocess.CalledProcessError as e:
        raise DownstreamFetchError(
            f"Failed to fetch branch {downstream_branch} from {downstream_url}"
        ) from e

    last_merged_rev = find_last_merged_rev(repo, upstream_rev, downstream_rev)
    logger.info("Last merged revision: %s", last_merged_rev)

    skip_revs = gerrit.get_skiplist(downstream_project, downstream_branch)
    commit_files_map = {}
    skipped_files_map = {}

    commits_to_copy, commit_files_map, skipped_files_map = find_commits_to_copy(
        repo,
        upstream_rev,
        last_merged_rev,
        skip_revs=skip_revs,
        exclude_file_patterns=exclude_file_patterns,
    )

    if not commits_to_copy:
        logger.info("Nothing to do!")
        return

    skipped_revs = []

    repo.checkout(downstream_rev)
    for i, rev in enumerate(reversed(commits_to_copy)):
        logger.info("(%s/%s) Cherry-pick %s", i + 1, len(commits_to_copy), rev)

        filtered_rev = None
        if skipped_files_map[rev]:
            filtered_rev = repo.filter_commit(
                rev=rev, files=commit_files_map[rev]
            )

        try:
            repo.cherry_pick(filtered_rev or rev)
        except EmptyCommitError:
            logger.warning("Skip cherry-pick due to empty commit")
            continue
        except MergeConflictError as e:
            logger.error("Merge conflict cherry-picking %s!", rev)
            if merge_conflict_behavior is MergeConflictBehavior.SKIP:
                logger.warning("Skipping %s", rev)
                skipped_revs.append(rev)
                continue
            raise MergeConflictsError(commits=[rev]) from e

        rewrite_commit_message(
            repo,
            upstream_rev=rev,
            change_id=pending_changes.get(rev) or gerrit.generate_change_id(),
            skipped_files=skipped_files_map[rev],
            prepend_subject=args.prepend_subject,
            sign_off=args.add_signed_off_by,
            keep_pseudoheaders=args.keep_pseudoheaders,
        )

    if repo.rev_parse() == downstream_rev:
        logger.info("Nothing to push!")
        return

    push_refspec = get_push_refspec(args, downstream_branch)
    if not args.dry_run:
        # We always want uploadvalidator~skip, since we're uploading
        # pre-existing third-party commits.
        try:
            repo.push(
                downstream_url, push_refspec, options=["uploadvalidator~skip"]
            )
        except subprocess.CalledProcessError as e:
            raise PushError(f"Failed to push to {downstream_url}") from e
    else:
        logger.info("Skip push due to dry run")

    if skipped_revs:
        revlist = [
            repo.log(rev, fmt="%H %s", num=1).stdout.strip()
            for rev in skipped_revs
        ]
        logger.error(
            "The following commits were not applied due to merge conflict:"
        )
        for rev in revlist:
            logger.error("- %s", rev)
        raise MergeConflictsError(commits=skipped_revs)


def write_json_error(path: pathlib.Path, err: Exception):
    """Write out the JSON-serialized protobuf from an exception.

    Args:
        path: The Path to write to.
        err: The exception to serialize.
    """
    err_json = {}
    if err:
        if isinstance(err, CopybotFatalError):
            err_json["failure_reason"] = err.enum_name
            if err.commits:
                err_json["merge_conflicts"] = [{"hash": x} for x in err.commits]
        else:
            err_json["failure_reason"] = CopybotFatalError.enum_name
    logger.debug("JSON response: %s", err_json)
    path.write_text(json.dumps(err_json))


def main(argv=None):
    """The entry point to the program."""
    parser = argparse.ArgumentParser(description="CopyBot")
    parser.add_argument(
        "--topic",
        help="Topic to set and search in Gerrit",
        default="copybot",
    )
    parser.add_argument(
        "--label",
        help="Label to set in Gerrit (can be passed multiple times)",
        action="append",
        dest="labels",
        default=[],
    )
    parser.add_argument(
        "--re",
        help="Reviewer to set in Gerrit (can be passed multiple times)",
        action="append",
        dest="reviewers",
        default=[],
    )
    parser.add_argument(
        "--cc",
        help="CC to set in Gerrit (can be passed multiple times)",
        action="append",
        dest="ccs",
        default=[],
    )
    parser.add_argument(
        "--ht",
        help="Hashtag to set in Gerrit (can be passed multiple times)",
        action="append",
        dest="hashtags",
        default=[],
    )
    parser.add_argument(
        "--json-out",
        type=pathlib.Path,
        help="Write JSON result to this file.",
    )
    parser.add_argument(
        "--dry-run",
        help="Don't push",
        action="store_true",
    )
    parser.add_argument(
        "--prepend-subject",
        help="Prepend the subject of commits made with this string",
        default="",
    )
    parser.add_argument(
        "--exclude-file-pattern",
        help="Exclude changes to files matched by these path regexes",
        action="append",
        dest="exclude_file_patterns",
        default=[],
    )
    parser.add_argument(
        "--merge-conflict-behavior",
        help="How to handle merge conflicts",
        default="SKIP",
        choices=[behavior.name for behavior in MergeConflictBehavior],
    )
    parser.add_argument(
        "--add-signed-off-by",
        help="Add Signed-off-by pseudoheader to commit messages",
        action="store_true",
    )
    parser.add_argument(
        "--keep-pseudoheader",
        help="Keep a pseudoheader from being prefixed",
        action="append",
        dest="keep_pseudoheaders",
        default=[],
    )
    parser.add_argument(
        "upstream",
        help="Upstream Git URL, optionally with a branch after colon",
    )
    parser.add_argument(
        "downstream",
        help="Downstream Git URL, optionally with a branch after colon",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s",
        level=logging.INFO,
    )

    err = None
    try:
        with tempfile.TemporaryDirectory(".copybot") as tmp_dir:
            run_copybot(args, tmp_dir)
    except Exception as e:
        err = e
        raise
    finally:
        if args.json_out:
            write_json_error(args.json_out, err)


if __name__ == "__main__":
    main()
