#!/usr/bin/env python3

# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint complains about module sh
# pylint: disable=import-error

"""Sets up the kernel-upstream repository

Necessary for automatic rebase (rebase.py)
"""

import os
import sys
import sh
import config
from githelpers import fetch, has_remote, add_remote

repo = 'kernel-upstream'
no_repo_msg = """No kernel-upstream repository!

Link the third_party/kernel/upstream repository as kernel-upstream. This link should
be relative so that it works both in cros SDK chroot and outside of it.
E.g. `ln -s ../../../../third_party/kernel/upstream/ kernel-upstream`

This is necessary for emerge-${BOARD} to be able to build the branches
created with the help of rebase.py. This process is not automated,
because work must be done outside of the directory of this project
and it's preferable that minimal assumptions are made about the outside
environment.

When you're done, re-run rebase_setup.py."""

if not os.path.exists(repo):
    print(no_repo_msg)
    sys.exit(1)

if not has_remote(repo, 'cros'):
    url = config.chromeos_repo
    add_remote(repo, 'cros', url)
    print('Added cros remote:', url)
else:
    print('cros remote ok')

if not has_remote(repo, 'upstream'):
    url = config.upstream_repo
    add_remote(repo, 'upstream', url)
    print('Added upstream remote: ', url)
else:
    print('upstream remote ok')

print('Fetching cros...')
fetch(repo, 'cros')

print('Fetching upstream...')
fetch(repo, 'upstream')

print('setting git config...')
with sh.pushd(repo):
    print('rerere.enabled = false')
    sh.git('config', 'rerere.enabled', 'false')
    print('rerere.autoupdate = false')
    sh.git('config', 'rerere.autoupdate', 'false')
    print('merge.renameLimit = 15345')
    sh.git('config', 'merge.renameLimit', '15345')
    print('diff.renameLimit = 15345')
    sh.git('config', 'diff.renameLimit', '15345')

print('Rebase setup OK')
