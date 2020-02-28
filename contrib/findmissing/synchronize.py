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

from common import UPSTREAM_PATH, CHROMEOS_PATH, STABLE_PATH, \
        UPSTREAM_REPO, CHROMEOS_REPO, STABLE_REPO, SUPPORTED_KERNELS, \
        stable_branch, chromeos_branch, update_kernel_db, Kernel


def synchronize_upstream():
    """Synchronizes locally cloned repo with linux upstream remote."""
    cwd = os.getcwd()
    destdir = os.path.join(cwd, UPSTREAM_PATH)
    repo = UPSTREAM_REPO

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


def synchronize_custom(path, repo):
    """Synchronizes locally cloned repo with linux stable/chromeos remote."""
    cwd = os.getcwd()
    destdir = os.path.join(cwd, path)
    upstream_destdir = os.path.join(cwd, UPSTREAM_PATH)

    get_branch = stable_branch if path == 'linux_stable' else chromeos_branch

    if not os.path.exists(destdir):
        print('Cloning %s into %s' % (repo, destdir))
        cmd = ('git clone %s %s' % (repo, destdir)).split(' ')
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        p.wait()

        os.chdir(destdir)
        for kernel in SUPPORTED_KERNELS:
            bname = get_branch(kernel)
            cmd = ('git checkout -b %s origin/%s' % (bname, bname)).split(' ')
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

        for kernel in SUPPORTED_KERNELS:
            branch = get_branch(kernel)
            cmd = ('git rev-parse --verify %s' % (branch)).split(' ')
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            p.wait()

            output, _ = p.communicate()
            if output:
                cmd = ('git checkout %s' % (branch)).split(' ')
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                p.wait()

                cmd = 'git pull'.split(' ')
                p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                p.wait()

                output, _ = p.communicate()
                if not output:
                    cmd = ('git reset --hard origin/%s' % (branch)).split(' ')
                    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
                    p.wait()
            else:
                cmd = ('git checkout -b %s origin/%s' % (branch, branch)).split(' ')
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
    db = MySQLdb.Connect(user='linux_patches_robot', host='127.0.0.1', db='linuxdb')
    print('updating upstreamdb')
    update_kernel_db(db, Kernel.linux_upstream)
    print('updating stabledb')
    update_kernel_db(db, Kernel.linux_stable)
    print('updating chromeosdb')
    update_kernel_db(db, Kernel.linux_chrome)
    db.close()
    print('FINISHED UPDATING DBS')


if __name__ == '__main__':
    synchronize_repositories()
    synchronize_database()
