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
import MySQLdb
import common

UPSTREAM_KERNEL_METADATA = common.get_kernel_metadata(common.Kernel.linux_upstream)
STABLE_KERNEL_METADATA = common.get_kernel_metadata(common.Kernel.linux_stable)
CHROME_KERNEL_METADATA = common.get_kernel_metadata(common.Kernel.linux_chrome)

def synchronize_upstream(upstream_kernel_metadata):
    """Synchronizes locally cloned repo with linux upstream remote."""
    destdir = common.get_kernel_absolute_path(upstream_kernel_metadata.path)
    repo = upstream_kernel_metadata.repo

    if not os.path.exists(destdir):
        print('Cloning %s into %s' % (repo, destdir))
        clone = ['git', 'clone', '-q', repo, destdir]
        subprocess.run(clone)
    else:
        os.chdir(destdir)

        print('Pulling latest changes in %s into %s' % (repo, destdir))
        checkout_master = ['git', 'checkout', '-q', 'master']
        pull = ['git', 'pull', '-q']
        subprocess.run(checkout_master)
        subprocess.run(pull)

    os.chdir(common.WORKDIR)


def synchronize_custom(custom_kernel_metadata):
    """Synchronizes locally cloned repo with linux stable/chromeos remote."""
    destdir = common.get_kernel_absolute_path(custom_kernel_metadata.path)
    upstream_destdir = common.get_kernel_absolute_path(common.UPSTREAM_PATH)
    repo = custom_kernel_metadata.repo

    get_branch_name = custom_kernel_metadata.get_kernel_branch

    if not os.path.exists(destdir):
        print('Cloning %s into %s' % (repo, destdir))
        clone = ['git', 'clone', '-q', repo, destdir]
        subprocess.run(clone)

        os.chdir(destdir)
        for branch in custom_kernel_metadata.branches:
            branch_name = get_branch_name(branch)

            print('Creating local branch %s in destdir %s' % (branch_name, destdir))
            checkout_branch = ['git', 'checkout', '-q', branch_name]
            subprocess.run(checkout_branch)

        print('Add remote upstream %s to destdir %s' % (upstream_destdir, destdir))
        add_upstream_remote = ['git', 'remote', 'add', 'upstream', upstream_destdir]
        fetch_upstream = ['git', 'fetch', '-q', 'upstream']
        subprocess.run(add_upstream_remote)
        subprocess.run(fetch_upstream)
    else:
        os.chdir(destdir)

        print('Updating %s into %s' % (repo, destdir))
        hard_reset = ['git', 'reset', '-q', '--hard', 'HEAD']
        fetch_origin = ['git', 'fetch', '-q', 'origin']
        subprocess.run(hard_reset)
        subprocess.run(fetch_origin)

        for branch in custom_kernel_metadata.branches:
            branch_name = get_branch_name(branch)
            print('Updating local branch %s in destdir %s' % (branch_name, destdir))
            checkout_branch = ['git', 'checkout', '-q', branch_name]
            pull = ['git', 'pull', '-q']
            subprocess.run(checkout_branch)
            subprocess.run(pull)

    os.chdir(common.WORKDIR)


def synchronize_repositories():
    """Deep clones linux_upstream, linux_stable, and linux_chromeos repositories"""
    synchronize_upstream(UPSTREAM_KERNEL_METADATA)
    synchronize_custom(STABLE_KERNEL_METADATA)
    synchronize_custom(CHROME_KERNEL_METADATA)


def synchronize_databases():
    """Synchronizes the databases for upstream, stable, and chromeos."""
    db = MySQLdb.Connect(user='linux_patches_robot', host='127.0.0.1', db='linuxdb')
    common.update_kernel_db(db, UPSTREAM_KERNEL_METADATA)
    common.update_kernel_db(db, STABLE_KERNEL_METADATA)
    common.update_kernel_db(db, CHROME_KERNEL_METADATA)
    db.close()


if __name__ == '__main__':
    synchronize_repositories()
    synchronize_databases()