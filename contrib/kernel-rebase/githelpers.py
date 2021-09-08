# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Disable pylint noise
# pylint: disable=E0401

"""Git helpers

Wraps several git functionalities via shell as simple python functions.
Additionally it implements an automatic conflict resolution system that
replaces git rerere for this project, due to specific requirements.
"""

import hashlib
import os
import re
import sh
from config import debug

GITHELPERS_DBG_PATH = 'debug/githelpers/'

if debug:
    sh.mkdir('-p', GITHELPERS_DBG_PATH)

def is_dirty(repo):
    """Check if repo is dirty"""

    with sh.pushd(repo):
        cmd = sh.git('--no-pager', 'status', '--short', '--porcelain')
    return str(cmd) != ''


def fetch(repo, remote):
    """fetch remote on repo"""

    with sh.pushd(repo):
        sh.git('fetch', remote)


def checkout(repo, branch):
    """checkout to a given branch on repo"""

    with sh.pushd(repo):
        sh.git('checkout', branch)


def create_head(repo, name):
    """creates a branch on repo"""

    with sh.pushd(repo):
        sh.git('branch', name)


def cherry_pick(repo, sha):
    """cherryp-pick sha on repo"""

    with sh.pushd(repo):
        # replace rerere-autoupdate to its negation after we finish migration to
        # patches stored in files
        ret = sh.git('cherry-pick', '--no-rerere-autoupdate', sha)
    if debug:
        sh.mkdir('-p', GITHELPERS_DBG_PATH + sha)
        with open(GITHELPERS_DBG_PATH + sha + '/cherry-pick', 'w') as f:
            f.write(str(ret))


def apply_patch(repo, diff, sha):
    """applies a patch in repo"""

    with sh.pushd(repo):
        ret = sh.git('am', '-3', '--no-rerere-autoupdate', diff)
    if debug:
        sh.mkdir('-p', GITHELPERS_DBG_PATH + sha)
        with open(GITHELPERS_DBG_PATH + sha + '/am', 'w') as f:
            f.write(str(ret))


def is_resolved(repo):
    """Checks if all conflicts are resolved"""
    with sh.pushd(repo):
        ret = sh.git('--no-pager', 'status', '--short', '--porcelain')
    ret = str(ret)
    # look up the short format of `git show` for details
    for l in ret.splitlines():
        if l[1] != ' ':
            return False
    return True

# if you change your hashing scheme, move the previous implementation to this fn
# During the next triage, all patches should get the re-calculated hashes and will
# be automatically renamed

def refine_text_old(text):
    """Cleans up a patch (old)

    Old function for cleaning up patch content,
    only used for a single rebase so that all patches can be
    appropriately renamed
    """

    lines = text.splitlines()
    refined = ''
    for l in lines:
        if not l.startswith('index '):
            refined += l + '\n'
    return refined


def refine_text(text):
    """removes all brittle content from a patch"""

    lines = text.splitlines()
    refined = ''
    for l in lines:
        line_num_delim2 = l.find('@@', 1)
        if line_num_delim2 != -1:
            # truncate cosmetic information from the line containing diff line
            # number
            l = l[0:line_num_delim2 + 2]
        if not l.startswith('index '):
            refined += l + '\n'
    return refined


def patch_title(repo, sha, old=False):
    """computes a unique hash for a given patch"""

    with sh.pushd(repo):
        ret = sh.git('--no-pager', 'show', '--format=', '--no-color', sha)
    text = str(ret)

    if old:
        refined = refine_text_old(text)
    else:
        refined = refine_text(text)
    sha224 = hashlib.sha224(refined.encode()).hexdigest()
    if debug:
        s = ''
        if old:
            s = '_old'
        sh.mkdir('-p', GITHELPERS_DBG_PATH + sha + s)
        with open(GITHELPERS_DBG_PATH + sha + s + '/text_all', 'w') as f:
            f.write(text)
        with open(GITHELPERS_DBG_PATH + sha + s + '/text_hashed', 'w') as f:
            f.write(refined)
        with open(GITHELPERS_DBG_PATH + sha + s + '/sha224', 'w') as f:
            f.write(sha224)
    return sha224


def patch_path(title):
    """transforms title of a patch into an appropriate path"""

    return 'patches/' + title + '.patch'


def head_diff(repo):
    """Gets the diff between HEAD~ and HEAD"""

    with sh.pushd(repo):
        diff = sh.git(
            '--no-pager',
            'format-patch',
            '--no-color',
            '--stdout',
            'HEAD~..HEAD')

    # Remove information about indices. Git uses this to autoresolve some
    # conflicts, which will only work if the indices refer to git objects
    # present locally. It's not portable, and thus has to be disabled.
    # It would be preferable to fix it with a git option instead of sabotaging
    # the patch file, but AFAICT it's not possible as of now.
    diff = re.sub(r'^index .*\n?', '', str(diff), flags=re.MULTILINE)

    return diff


def head_sha(repo):
    """Gets the sha of HEAD"""

    with sh.pushd(repo):
        sha = sh.git('--no-pager', 'rev-parse', '--short', 'HEAD')

    return str(sha).strip('\n')


def save_head(repo, sha, path_override=None):
    """Saves the current diff as a conflict resolution"""

    diff = head_diff(repo)
    if path_override is None:
        title = patch_title(repo, sha)
        path = patch_path(title)
    else:
        path = path_override
    print('Saving patch', sha, 'as', path)
    with open(path, 'w') as f:
        f.write(diff)


def commit_message(repo, sha):
    """Gets a commit message"""

    with sh.pushd(repo):
        msg = sh.git('--no-pager', 'show', '--no-color', '--format=medium', '--quiet', sha)

    return str(msg)

def replacement(repo, sha):
    """Check if there exists a saved conflict resolution for a given patch"""

    title = patch_title(repo, sha)
    path = patch_path(title)
    if os.path.exists(path):
        return path

    title_old = patch_title(repo, sha, True)
    path_old = patch_path(title_old)
    if os.path.exists(path_old):
        print('Found patch using the old hashing scheme:', path_old)
        print('Rename to:', path)
        sh.mv(path_old, path)
        return path

    return None


def cp_or_am_in_progress(repo):
    """Check if a cherry-pick or am is in progress in repo"""

    with sh.pushd(repo):
        cmd = sh.git('--no-pager', 'status')
    out = str(cmd)
    cp = 'You are currently cherry-picking commit' in out
    am = 'You are in the middle of an am session' in out

    return cp or am

def has_remote(repo, remote):
    """Check if a repo has a remote with the given name"""
    with sh.pushd(repo):
        remotes = str(sh.git('remote', '-v'))
    for entry in remotes.splitlines():
        if entry.split()[0] == remote:
            return True
    return False

def add_remote(repo, remote, url):
    """Adds a remote to the repo"""
    with sh.pushd(repo):
        sh.git('remote', 'add', remote, url)
