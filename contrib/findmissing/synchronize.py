#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Setup module containing script to Synchronize kernel repositories + database.

TODO(hirthanan): abstract out subprocess calls to function to take cmd + block
"""

from __future__ import print_function
import os
import subprocess
import MySQLdb
import common
import missing

UPSTREAM_KERNEL_METADATA = common.get_kernel_metadata(common.Kernel.linux_upstream)
STABLE_KERNEL_METADATA = common.get_kernel_metadata(common.Kernel.linux_stable)
CHROME_KERNEL_METADATA = common.get_kernel_metadata(common.Kernel.linux_chrome)

def synchronize_upstream(upstream_kernel_metadata):
    """Synchronizes locally cloned repo with linux upstream remote."""
    cwd = os.getcwd()
    path = upstream_kernel_metadata.path
    destdir = os.path.join(cwd, path)
    repo = upstream_kernel_metadata.repo

    print(destdir, repo, cwd)

    if not os.path.exists(destdir):
        print('Cloning %s into %s' % (repo, destdir))
        cmd = ('git clone %s %s' % (repo, destdir)).split(' ')
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        p.wait()

    else:
        os.chdir(destdir)

        print('Updating %s into %s' % (repo, destdir))
        cmd = 'git checkout master; git pull'.split(' ')
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        p.wait()

    os.chdir(cwd)


def synchronize_custom(custom_kernel_metadata):
    """Synchronizes locally cloned repo with linux stable/chromeos remote."""
    path = custom_kernel_metadata.path
    repo = custom_kernel_metadata.repo

    cwd = os.getcwd()
    destdir = os.path.join(cwd, path)
    upstream_destdir = os.path.join(cwd, common.UPSTREAM_PATH)

    get_branch_name = custom_kernel_metadata.get_kernel_branch

    if not os.path.exists(destdir):
        print('Cloning %s into %s' % (repo, destdir))
        cmd = ('git clone %s %s' % (repo, destdir)).split(' ')
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        p.wait()

        os.chdir(destdir)
        for branch in custom_kernel_metadata.branches:
            branch_name = get_branch_name(branch)
            cmd = ('git checkout -b %s origin/%s' % (branch_name, branch_name)).split(' ')
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            p.wait()

        cmd = 'git remote add upstream %s; git fetch upstream' % (upstream_destdir)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        p.wait()

    else:
        os.chdir(destdir)

        print('Updating %s into %s' % (repo, destdir))
        cmd = 'git reset --hard HEAD; git fetch origin'
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True)
        p.wait()

        for branch in custom_kernel_metadata.branches:
            branch_name = get_branch_name(branch)
            cmd = ('git rev-parse --verify %s' % (branch_name)).split(' ')
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            p.wait()

            output, _ = p.communicate()
            if output:
                cmd = ('git checkout %s' % (branch_name)).split(' ')
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                p.wait()

                cmd = 'git pull'.split(' ')
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                p.wait()

                output, _ = p.communicate()
                if not output:
                    cmd = ('git reset --hard origin/%s' % (branch_name)).split(' ')
                    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                    p.wait()
            else:
                cmd = ('git checkout -b %s origin/%s' % (branch_name, branch_name)).split(' ')
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                p.wait()

    os.chdir(cwd)


def synchronize_repositories():
    """Deep clones linux_upstream, linux_stable, and linux_chromeos repositories"""
    synchronize_upstream(UPSTREAM_KERNEL_METADATA)
    synchronize_custom(STABLE_KERNEL_METADATA)
    synchronize_custom(CHROME_KERNEL_METADATA)


def synchronize_database():
    """Synchronizes the databases for upstream, stable, and chromeos."""
    db = MySQLdb.Connect(user='linux_patches_robot', host='127.0.0.1', db='linuxdb')
    common.update_kernel_db(db, UPSTREAM_KERNEL_METADATA)
    common.update_kernel_db(db, STABLE_KERNEL_METADATA)
    common.update_kernel_db(db, CHROME_KERNEL_METADATA)
    missing.missing(db)
    db.close()


if __name__ == '__main__':
    synchronize_repositories()
    synchronize_database()
