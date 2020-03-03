#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Setup module containing script to Synchronize kernel repositories + database."""

from __future__ import print_function
import os
import subprocess

from common import UPSTREAM_PATH, CHROMEOS_PATH, STABLE_PATH, \
        UPSTREAM_REPO, CHROMEOS_REPO, STABLE_REPO, \
        SUPPORTED_KERNELS, stable_branch, chromeos_branch

from initdb_upstream import update_upstreamdb
from initdb_stable import update_stabledb
from initdb_chromeos import update_chromeosdb


def synchronize_upstream():
    """Synchronizes locally cloned repo with linux upstream remote."""
    cwd = os.getcwd()
    destdir = os.path.join(cwd, UPSTREAM_PATH)
    repo = UPSTREAM_REPO

    print(destdir, repo, cwd)

    if not os.path.exists(destdir):
        print(f'Cloning {repo} into {destdir}')
        cmd = f'git clone {repo} {destdir}'.split(' ')
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        p.wait()

    else:
        os.chdir(destdir)

        print(f'Updating {repo} into {destdir}')
        cmd = 'git checkout master; git pull'.split(' ')
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        p.wait()

    os.chdir(cwd)


def synchronize_custom(path, repo):
    """Synchronizes locally cloned repo with linux stable/chromeos remote."""
    cwd = os.getcwd()
    destdir = os.path.join(cwd, path)
    upstream_destdir = os.path.join(cwd, UPSTREAM_PATH)

    get_branch = stable_branch if path == 'linux_stable' else chromeos_branch

    if not os.path.exists(destdir):
        print(f'Cloning {repo} into {destdir}')
        cmd = f'git clone {repo} {destdir}'.split(' ')
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        p.wait()

        os.chdir(destdir)
        for kernel in SUPPORTED_KERNELS:
            cmd = f'git checkout -b {get_branch(kernel)} origin/{get_branch(kernel)}'.split(' ')
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            p.wait()

        cmd = f'git remote add upstream {upstream_destdir}; git fetch upstream'
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        p.wait()

    else:
        os.chdir(destdir)

        print(f'Updating {repo} into {destdir}')
        cmd = 'git reset --hard HEAD; git fetch origin'
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        p.wait()

        for kernel in SUPPORTED_KERNELS:
            branch = get_branch(kernel)
            cmd = f'git rev-parse --verify {branch}'.split(' ')
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            p.wait()

            output, _ = p.communicate()
            if output:
                cmd = f'git checkout {branch}'.split(' ')
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                p.wait()

                cmd = 'git pull'.split(' ')
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                p.wait()

                output, _ = p.communicate()
                if not output:
                    cmd = f'git reset --hard origin/{branch}'.split(' ')
                    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                    p.wait()
            else:
                cmd = f'git checkout -b {branch} origin/{branch}'.split(' ')
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                p.wait()

    os.chdir(cwd)


def synchronize_repositories():
    """Deep clones linux_upstream, linux_stable, and linux_chromeos repositories"""
    synchronize_upstream()
    synchronize_custom(STABLE_PATH, STABLE_REPO)
    synchronize_custom(CHROMEOS_PATH, CHROMEOS_REPO)

def synchronize_database():
    """Synchronizes the databases for upstream, stable, and chromeos."""
    update_upstreamdb()
    update_stabledb()
    update_chromeosdb()


if __name__ == '__main__':
    synchronize_repositories()
    synchronize_database()
