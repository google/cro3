#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module create database used to track bug data in the chromeos repo."""

from __future__ import print_function


def make_table(c):
    """Create database table."""

    c.execute('CREATE TABLE patches ('
            'id INTEGER PRIMARY KEY,'
            'downstream_sha text,'
            'usha text,'
            'fix_usha text,'
            'downstream_link text,'
            'fix_link text,'
            'status char(4))')

    c.execute('CREATE TABLE statistics ('
            'day int,'
            'clean_fix_count int,'
            'fail_fix_count text,')



def get_reviewers(chromeos_sha):
    """Retrieves list of reviewers from gerrit given a chromeos commit sha."""
    print(chromeos_sha)
    return []


def create_analysis_entry():
    """Adds the daily entry for analysis of patch data into statistics db."""
    pass


def create_gerrit_change():
    """Uses gerrit api to handle creating gerrit tickets.

    Determines whether a ticket for a fix has already been created,
    and avoids duplicate creations.
    """

    chromeos_sha = None
    reviewers = get_reviewers(chromeos_sha)

    # Call gerrit api to create new change ticket if neccessary
    print('Calling gerrit api', reviewers)
    return


def update_patchesdb():
    """Create patchesdb for each chromeos kernel version."""
    pass


if __name__ == '__main__':
    update_patchesdb()
