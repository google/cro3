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
import os
import re
import subprocess
import common


def reset_head_hard():
    """Force reset to git head"""
    reset_head_cmd = ['git', 'reset', '-q', '--hard', 'HEAD']
    subprocess.run(reset_head_cmd, check=True)


def checkout_and_clean(branch):
    """Cleanup uncommitted files in branch and checkout to be up to date with origin."""
    clean_untracked = ['git', 'clean', '-d', '-x', '-f', '-q']
    checkout = ['git', 'checkout', '-q', branch]
    reset_origin = ['git', 'reset', '-q', '--hard', 'origin/%s' % branch]
    current = ['git', 'symbolic-ref', '-q', '--short', 'HEAD']

    reset_head_hard()
    subprocess.run(clean_untracked, check=True)

    current_branch = subprocess.check_output(current, encoding='utf-8', errors='ignore').rstrip()
    if current_branch != branch:
        subprocess.run(checkout, check=True)

    subprocess.run(reset_origin, check=True)


def get_upstream_fullsha(abbrev_sha):
    """Returns the full upstream sha for an abbreviated 12 digit sha using git cli"""
    upstream_absolute_path = common.get_kernel_absolute_path(common.UPSTREAM_PATH)
    try:
        cmd = ['git', '-C', upstream_absolute_path, 'rev-parse', abbrev_sha]
        full_sha = subprocess.check_output(cmd, encoding='utf-8')
        return full_sha.rstrip()
    except subprocess.CalledProcessError as e:
        raise type(e)('Could not find full upstream sha for %s' % abbrev_sha, e.cmd) from e


def get_commit_message(kernel_path, sha):
    """Returns the commit message for a sha in a given local path to kernel."""
    try:
        cmd = ['git', '-C', kernel_path, 'log',
                '--format=%B', '-n', '1', sha]
        commit_message = subprocess.check_output(cmd, encoding='utf-8', errors='ignore')

        # Single newline following commit message
        return commit_message.rstrip() + '\n'
    except subprocess.CalledProcessError as e:
        raise type(e)('Couldnt retrieve commit in kernel path %s for sha %s'
                        % (kernel_path, sha), e.cmd) from e


def get_upstream_commit_message(upstream_sha):
    """Returns the commit message for a given upstream sha using git cli."""
    upstream_absolute_path = common.get_kernel_absolute_path(common.UPSTREAM_PATH)
    return get_commit_message(upstream_absolute_path, upstream_sha)


def get_chrome_commit_message(chrome_sha):
    """Returns the commit message for a given chrome sha using git cli."""
    chrome_absolute_path = common.get_kernel_absolute_path(common.CHROMEOS_PATH)
    return get_commit_message(chrome_absolute_path, chrome_sha)


def get_merge_sha(branch, sha):
    """Returns SHA of merge commit for provided SHA if available"""

    chrome_absolute_path = common.get_kernel_absolute_path(common.CHROMEOS_PATH)

    try:
        # Get list of merges in <branch> since <sha>
        cmd = ['git', '-C', chrome_absolute_path, 'log', '--format=%h', '--abbrev=12',
               '--ancestry-path', '--merges', '%s..%s' % (sha, branch)]
        sha_list = subprocess.check_output(cmd, encoding='utf-8', errors='ignore',
                                           stderr=subprocess.DEVNULL)
        if not sha_list:
            logging.info('No merge commit for sha %s in branch %s', sha, branch)
            return None
        # merge_sha is our presumed merge commit
        merge_sha = sha_list.splitlines()[-1]
        # Verify if <sha> is indeed part of the merge
        cmd = ['git', '-C', chrome_absolute_path, 'log', '--format=%h', '--abbrev=12',
               '%s~1..%s' % (merge_sha, merge_sha)]
        sha_list = subprocess.check_output(cmd, encoding='utf-8', errors='ignore',
                                           stderr=subprocess.DEVNULL)
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
        cmd = ['git', '-C', chrome_absolute_path, 'log', '--format=%B', '-n', '1', kernel_sha]
        commit_message = subprocess.check_output(cmd, encoding='utf-8', errors='ignore')

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
        cmd = ['git', '-C', absolute_path, 'log', '--format=%B', '-n', '1', sha]
        commit_message = subprocess.check_output(cmd, encoding='utf-8', errors='ignore')
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


def get_git_push_cmd(chromeos_branch, reviewers):
    """Generates git push command with added reviewers and autogenerated tag.

    Read more about gerrit tags here:
        https://gerrit-review.googlesource.com/Documentation/cmd-receive-pack.html
    """
    git_push_head = 'git push origin HEAD:refs/for/%s' % chromeos_branch
    reviewers_tag = ['r=%s'% r for r in reviewers]
    autogenerated_tag = ['t=autogenerated']
    tags = ','.join(reviewers_tag + autogenerated_tag)
    return git_push_head + '%' + tags


def cherry_pick_and_push_fix(fixer_upstream_sha, fixer_changeid, chromeos_branch,
                                fix_commit_message, reviewers):
    """Cherry picks upstream commit into chrome repo.

    Adds reviewers and autogenerated tag with the pushed commit.
    """
    cwd = os.getcwd()
    chrome_absolute_path = common.get_kernel_absolute_path(common.CHROMEOS_PATH)

    # reset linux_chrome repo to remove local changes
    try:
        os.chdir(chrome_absolute_path)
        checkout_and_clean(chromeos_branch)
        subprocess.run(['git', 'cherry-pick', '-n', fixer_upstream_sha], check=True)
        subprocess.run(['git', 'commit', '-s', '-m', fix_commit_message], check=True)

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
        subprocess.run(['git', 'commit', '--amend', '-m', commit_message], check=True)

        git_push_cmd = get_git_push_cmd(chromeos_branch, reviewers)
        subprocess.run(git_push_cmd.split(' '), check=True)

        return fixer_changeid
    except subprocess.CalledProcessError as e:
        raise ValueError('Failed to cherrypick and push upstream fix %s on branch %s'
                        % (fixer_upstream_sha, chromeos_branch)) from e
    finally:
        reset_head_hard()
        os.chdir(cwd)


def search_subject_in_branch(merge_base, sha):
    """Check if sha subject line is in the current branch.

    Assumes function is run from correct directory/branch.
    """

    try:
        # Retrieve subject line of provided SHA
        cmd = ['git', 'log', '--pretty=format:%s', '-n', '1', sha]
        subject = subprocess.check_output(cmd, encoding='utf-8', errors='ignore')
    except subprocess.CalledProcessError:
        logging.error('Error locating subject for sha %s', sha)
        raise

    try:
        cmd = ['git', 'log', '--no-merges', '-F', '--grep', subject,
               '%s..' % merge_base]
        result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        return bool(result)
    except subprocess.CalledProcessError:
        logging.error('Error while searching for subject "%s"', subject)
        raise


def get_cherrypick_status(repository, merge_base, branch, sha, apply=True):
    """cherry-pick provided sha into provided repository and branch.

    Return Status Enum:
    MERGED if the patch has already been applied,
    OPEN if the patch is missing and applies cleanly,
    CONFLICT if the patch is missing and fails to apply.
    """
    # Save current working directory
    cwd = os.getcwd()

    # Switch to repository directory to apply cherry-pick
    absolute_path = common.get_kernel_absolute_path(repository)

    os.chdir(absolute_path)
    checkout_and_clean(branch)

    ret = None
    try:
        applied = search_subject_in_branch(merge_base, sha)
        if applied:
            ret = common.Status.MERGED
            raise ValueError

        if not apply:
            raise ValueError

        result = subprocess.call(['git', 'cherry-pick', '-n', sha],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        if result:
            ret = common.Status.CONFLICT
            raise ValueError

        diff = subprocess.check_output(['git', 'diff', 'HEAD'])
        if diff:
            ret = common.Status.OPEN
            raise ValueError

        ret = common.Status.MERGED

    except ValueError:
        pass

    except subprocess.CalledProcessError:
        ret = common.Status.CONFLICT

    finally:
        reset_head_hard()
        os.chdir(cwd)

    return ret


# match "vX.Y[.Z][.rcN]"
version = re.compile(r'(v[0-9]+(?:\.[0-9]+)+(?:-rc[0-9]+)?)\s*')

def get_integrated_tag(sha):
    """For a given SHA, find the first tag that includes it."""

    try:
        path = common.get_kernel_absolute_path(common.UPSTREAM_PATH)
        cmd = ['git', '-C', path, 'describe', '--match', 'v*',
               '--contains', sha]
        tag = subprocess.check_output(cmd, encoding='utf-8',
                                      stderr=subprocess.DEVNULL)
        return version.match(tag).group()
    except AttributeError:
        return None
    except subprocess.CalledProcessError:
        return None
