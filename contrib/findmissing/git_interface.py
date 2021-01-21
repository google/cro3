#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing methods interfacing with git

i.e Parsing git logs for change-id, full commit sha's, etc.
"""

from __future__ import print_function
import logging
import re
import subprocess
import common


def _git_check_output(path, command):
    git_cmd = ['git', '-C', path] + command
    return subprocess.check_output(git_cmd, encoding='utf-8', errors='ignore',
                                   stderr=subprocess.DEVNULL)


def get_upstream_fullsha(abbrev_sha):
    """Returns the full upstream sha for an abbreviated 12 digit sha using git cli"""
    upstream_absolute_path = common.get_kernel_absolute_path(common.UPSTREAM_PATH)
    try:
        cmd = ['rev-parse', abbrev_sha]
        full_sha = _git_check_output(upstream_absolute_path, cmd)
        return full_sha.rstrip()
    except subprocess.CalledProcessError as e:
        raise type(e)('Could not find full upstream sha for %s' % abbrev_sha, e.cmd) from e


def _get_commit_message(kernel_path, sha):
    """Returns the commit message for a sha in a given local path to kernel."""
    try:
        cmd = ['log', '--format=%B', '-n', '1', sha]
        commit_message = _git_check_output(kernel_path, cmd)

        # Single newline following commit message
        return commit_message.rstrip() + '\n'
    except subprocess.CalledProcessError as e:
        raise type(e)('Couldnt retrieve commit in kernel path %s for sha %s'
                        % (kernel_path, sha), e.cmd) from e


def get_upstream_commit_message(upstream_sha):
    """Returns the commit message for a given upstream sha using git cli."""
    upstream_absolute_path = common.get_kernel_absolute_path(common.UPSTREAM_PATH)
    return _get_commit_message(upstream_absolute_path, upstream_sha)


def get_chrome_commit_message(chrome_sha):
    """Returns the commit message for a given chrome sha using git cli."""
    chrome_absolute_path = common.get_kernel_absolute_path(common.CHROMEOS_PATH)
    return _get_commit_message(chrome_absolute_path, chrome_sha)


def get_merge_sha(branch, sha):
    """Returns SHA of merge commit for provided SHA if available"""

    chrome_absolute_path = common.get_kernel_absolute_path(common.CHROMEOS_PATH)

    try:
        # Get list of merges in <branch> since <sha>
        cmd = ['log', '--format=%h', '--abbrev=12', '--ancestry-path', '--merges',
               '%s..%s' % (sha, branch)]
        sha_list = _git_check_output(chrome_absolute_path, cmd)
        if not sha_list:
            logging.info('No merge commit for sha %s in branch %s', sha, branch)
            return None
        # merge_sha is our presumed merge commit
        merge_sha = sha_list.splitlines()[-1]
        # Verify if <sha> is indeed part of the merge
        cmd = ['log', '--format=%h', '--abbrev=12', '%s~1..%s' % (merge_sha, merge_sha)]
        sha_list = _git_check_output(chrome_absolute_path, cmd)
        if sha_list and sha in sha_list.splitlines():
            return merge_sha
        logging.info('Merge commit for sha %s found as %s, but sha is missing in merge',
                     sha, merge_sha)

    except subprocess.CalledProcessError as e:
        logging.info('Error "%s" while trying to find merge commit for sha %s in branch %s',
                     e, sha, branch)

    return None


def get_commit_changeid_linux_chrome(kernel_sha):
    """Returns the changeid of the kernel_sha commit by parsing linux_chrome git log.

    kernel_sha will be one of linux_stable or linux_chrome commits.
    """
    chrome_absolute_path = common.get_kernel_absolute_path(common.CHROMEOS_PATH)
    try:
        cmd = ['log', '--format=%B', '-n', '1', kernel_sha]
        commit_message = _git_check_output(chrome_absolute_path, cmd)

        m = re.findall('^Change-Id: (I[a-z0-9]{40})$', commit_message, re.M)

        # Get last change-id in case chrome sha cherry-picked/reverted into new commit
        return m[-1]
    except subprocess.CalledProcessError as e:
        raise type(e)('Couldnt retrieve changeid for commit %s' % kernel_sha, e.cmd) from e
    except IndexError as e:
        # linux_stable kernel_sha's do not have an associated ChangeID
        return None


def get_tag_emails_linux_chrome(sha):
    """Returns unique list of chromium.org or google.com e-mails.

    The returned lust of e-mails is associated with tags found after
    the last 'cherry picked from commit' message in the commit identified
    by sha. Tags and e-mails are found by parsing the commit log.

    sha is expected to be be a commit in linux_stable or in linux_chrome.
    """
    absolute_path = common.get_kernel_absolute_path(common.CHROMEOS_PATH)
    try:
        cmd = ['log', '--format=%B', '-n', '1', sha]
        commit_message = _git_check_output(absolute_path, cmd)
        # If the commit has been cherry-picked, use subsequent tags to create
        # list of reviewers. Otherwise, use all tags. Either case, only return
        # e-mail addresses from Google domains.
        s = commit_message.split('cherry picked from commit')
        tags = 'Signed-off-by|Reviewed-by|Tested-by|Commit-Queue'
        domains = 'chromium.org|google.com'
        m = '^(?:%s): .* <(.*@(?:%s))>$' % (tags, domains)
        emails = re.findall(m, s[-1], re.M)
        if not emails:
            # Final fallback: In some situations, "cherry picked from"
            # is at the very end of the commit description, with no
            # subsequent tags. If that happens, look for tags in the
            # entire description.
            emails = re.findall(m, commit_message, re.M)
        return list(set(emails))
    except subprocess.CalledProcessError as e:
        raise type(e)('Could not retrieve tag e-mails for commit %s' % sha, e.cmd) from e
    except IndexError:
        # sha does do not have a recognized tag
        return None


# match "vX.Y[.Z][.rcN]"
version = re.compile(r'(v[0-9]+(?:\.[0-9]+)+(?:-rc[0-9]+)?)\s*')

def get_integrated_tag(sha):
    """For a given SHA, find the first upstream tag that includes it."""

    try:
        path = common.get_kernel_absolute_path(common.UPSTREAM_PATH)
        cmd = ['describe', '--match', 'v*', '--contains', sha]
        tag = _git_check_output(path, cmd)
        return version.match(tag).group()
    except AttributeError:
        return None
    except subprocess.CalledProcessError:
        return None


class commitHandler:
    """Class to control active accesses on a git repository"""

    def __init__(self, kernel, branch=None):
        self.metadata = common.get_kernel_metadata(kernel)
        if not branch:
            branch = self.metadata.branches[0]
        self.branch = branch
        self.merge_base = self.metadata.tag_template % branch
        self.branchname = self.metadata.get_kernel_branch(branch)
        self.path = common.get_kernel_absolute_path(self.metadata.path)
        self.status = 'unknown'
        self.commit_list = { }  # indexed by merge_base

        current_branch_cmd = ['symbolic-ref', '-q', '--short', 'HEAD']
        self.current_branch = self.__git_check_output(current_branch_cmd).rstrip()

    def __git_command(self, command):
        return ['git', '-C', self.path] + command

    def __git_check_output(self, command):
        cmd = self.__git_command(command)
        return subprocess.check_output(cmd, encoding='utf-8', errors='ignore')

    def __git_run(self, command):
        cmd = self.__git_command(command)
        subprocess.run(cmd, check=True)

    def __set_branch(self, branch):
        """Set the active branch"""
        if branch != self.branch:
            self.branch = branch
            self.merge_base = self.metadata.tag_template % branch
            self.branchname = self.metadata.get_kernel_branch(branch)
            self.status = 'unknown'

    def __reset_hard_ref(self, reference):
        """Force reset to provided reference"""
        reset_cmd = ['reset', '-q', '--hard', reference]
        self.__git_run(reset_cmd)

    def __reset_hard_head(self):
        """Force hard reset to git head in checked out branch"""
        self.__reset_hard_ref('HEAD')

    def __reset_hard_origin(self):
        """Force hard reset to head of remote branch"""
        self.__reset_hard_ref('origin/%s' % self.branchname)

    def __checkout_and_clean(self):
        """Clean up uncommitted files in branch and checkout to be up to date with origin."""
        clean_untracked = ['clean', '-d', '-x', '-f', '-q']
        checkout = ['checkout', '-q', self.branchname]

        self.__reset_hard_head()
        self.__git_run(clean_untracked)

        if self.current_branch != self.branchname:
            self.__git_run(checkout)
            self.current_branch = self.branchname

        self.__reset_hard_origin()

    def __setup(self):
        """Local setup function, to be called for each access"""
        if self.status == 'unknown':
            self.__checkout_and_clean()
        elif self.status == 'changed':
            self.__reset_hard_origin()

        self.status = 'clean'

    def __search_subject(self, sha):
        """Check if subject associated with 'sha' exists in the current branch"""

        try:
            # Retrieve subject line of provided SHA
            cmd = ['log', '--pretty=format:%s', '-n', '1', sha]
            subject = self.__git_check_output(cmd)
        except subprocess.CalledProcessError:
            logging.error('Failed to get subject for sha %s', sha)
            return False

        if self.branch not in self.commit_list:
            cmd = ['log', '--no-merges', '--format=%s',
                   '%s..%s' % (self.merge_base, self.branchname)]
            subjects = self.__git_check_output(cmd)
            self.commit_list[self.branch] = subjects.splitlines()

        # The following is a raw search which will match, for example, a revert of a commit.
        # A better method to check if commits have been applied would be desirable.
        subjects = self.commit_list[self.branch]
        return any(subject in s for s in subjects)

    def __get_git_push_cmd(self, reviewers):
        """Generates git push command with added reviewers and autogenerated tag.

        Read more about gerrit tags here:
            https://gerrit-review.googlesource.com/Documentation/cmd-receive-pack.html
        """
        reviewers_tag = ['r=%s'% r for r in reviewers]
        autogenerated_tag = ['t=autogenerated']
        tags = ','.join(reviewers_tag + autogenerated_tag)
        head = 'HEAD:refs/for/%s%%%s' % (self.branchname, tags)
        return ['push', 'origin', head]

    def fetch(self, remote=None):
        """Fetch changes from provided remote or from origin"""
        if not remote:
            remote = 'origin'
        self.__setup()
        fetch_cmd = ['fetch', '-q', remote]
        self.__git_run(fetch_cmd)
        self.status = 'changed'

    def pull(self, branch=None):
        """Pull changes from remote repository into provided or default branch"""
        if branch:
            self.__set_branch(branch)
        self.__setup()
        pull_cmd = ['pull', '-q']
        self.__git_run(pull_cmd)

    def cherry_pick_and_push(self, fixer_upstream_sha, fixer_changeid, fix_commit_message,
                             reviewers):
        """Cherry picks upstream commit into chrome repo.

        Adds reviewers and autogenerated tag with the pushed commit.
        """

        self.__setup()
        try:
            self.status = 'changed'
            self.__git_run(['cherry-pick', '-n', fixer_upstream_sha])
            self.__git_run(['commit', '-s', '-m', fix_commit_message])

            # commit has been cherry-picked and committed locally, precommit hook
            # in git repository adds changeid to the commit message. Pick it unless
            # we already have one passed as parameter.
            if not fixer_changeid:
                fixer_changeid = get_commit_changeid_linux_chrome('HEAD')

            # Sometimes the commit hook doesn't attach the Change-Id to the last
            # paragraph in the commit message. This seems to happen if the commit
            # message includes '---' which would normally identify the start of
            # comments. If the Change-Id is not in the last paragraph, uploading
            # the patch is rejected by Gerrit. Force-move the Change-Id to the end
            # of the commit message to solve the problem. This conveniently also
            # replaces the auto-generated Change-Id with the optional Change-Id
            # passed as parameter.
            commit_message = get_chrome_commit_message('HEAD')
            commit_message = re.sub(r'Change-Id:.*\n?', '', commit_message)
            commit_message = commit_message.rstrip()
            commit_message += '\nChange-Id: %s' % fixer_changeid
            self.__git_run(['commit', '--amend', '-m', commit_message])

            git_push_cmd = self.__get_git_push_cmd(reviewers)
            self.__git_run(git_push_cmd)

            return fixer_changeid
        except subprocess.CalledProcessError as e:
            raise ValueError('Failed to cherrypick and push upstream fix %s on branch %s'
                             % (fixer_upstream_sha, self.branchname)) from e
        finally:
            self.__reset_hard_head()
            self.status = 'changed'

    def cherrypick_status(self, sha, branch=None, apply=True):
        """cherry-pick provided sha into repository and branch identified by this class instance

        Return Status Enum:
        MERGED if the patch has already been applied,
        OPEN if the patch is missing and applies cleanly,
        CONFLICT if the patch is missing and fails to apply.
        """

        if branch:
            self.__set_branch(branch)

        self.__setup()

        ret = None
        try:
            applied = self.__search_subject(sha)
            if applied:
                ret = common.Status.MERGED
                raise ValueError

            if not apply:
                raise ValueError

            result = subprocess.call(self.__git_command(['cherry-pick', '-n', sha]),
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
            if result:
                ret = common.Status.CONFLICT
                raise ValueError

            diff = self.__git_check_output(['diff', 'HEAD'])
            if diff:
                ret = common.Status.OPEN
                raise ValueError

            ret = common.Status.MERGED

        except ValueError:
            pass

        except subprocess.CalledProcessError:
            ret = common.Status.CONFLICT

        finally:
            self.__reset_hard_head()
            self.status = 'clean'

        return ret
