#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Web server performing operations on our systems.

Systems will include: CloudSQL, CloudSource, and AppEngine.
"""

from __future__ import print_function

# if you are getting a linter error when uploading to gerrit from chroot env
#  run command: `sudo emerge flask` and reupload your changes.
from flask import Flask


app = Flask(__name__)

GERRIT_CHROMIUM_URL = 'https://chromium-review.googlesource.com/'
GERRIT_CHROMIUM_KERNEL_URL = ('https://chromium-review.googlesource.com/admin/'
        'repos/chromiumos/third_party/kernel,branches')

@app.route('/', methods=['GET'])
def home():
    """Test route for status check on compute engine"""
    return 'hello, compute engine are you there?'

@app.route('/sync/<string:version>', methods=['POST'])
def sync_version_table(version):
    """Updates the table for a kernel version."""
    print(version)


@app.route('/sync/patch-table/<string:version>', methods=['POST'])
def sync_patches(version):
    """Updates the patches table with new data for a kernel version."""
    print(version)


@app.route('/sync/linux-cloudsource', methods=['POST'])
def post_sync_linux():
    """Syncs linux-upstream, linux-stable, and linux-chromeos.

    These repositories are mirrored on cloudsource to avoid fully
    cloning the repositories every time we need to parse logs.
    """
    pass


@app.route('/statistics/daily', methods=['POST'])
def post_daily_stat():
    """Add daily statistics entry to patchesdb (statistics table)."""

    # Check number of entries in database
    day = 0

    if day < 1:
        # no entries in db yet
        pass
    elif 1 <= day < 366:
        # db contains less than a years worth of statistics
        pass
    else:
        # remove day 1 and add another entry
        pass
