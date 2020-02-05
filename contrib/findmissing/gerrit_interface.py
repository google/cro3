#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing methods interfacing with gerrit.

i.e Create new bugfix change tickets, and reading metadata about a specific change.
"""

from __future__ import print_function

import json
import requests

from config import CHROMIUM_REVIEW_BASEURL


def get_commit(changeid):
    """Retrieves current commit message for a change.

    May add some additional information to the fix patch for tracking purposes.
    i.e attaching a tag
    """
    get_commit_endpoint = (f'{CHROMIUM_REVIEW_BASEURL}/changes/{changeid}/'
            'revisions/current/commit')

    resp = requests.get(get_commit_endpoint)
    resp_json = json.loads(resp.text[5:])

    return resp_json


def get_reviewers(changeid):
    """Retrieves list of reviewers from gerrit given a chromeos changeid."""
    list_reviewers_endpoint = (f'{CHROMIUM_REVIEW_BASEURL}/changes/{changeid}/'
            'reviewers/')

    resp = requests.get(list_reviewers_endpoint)
    resp_json = json.loads(resp.text[5:])

    return resp_json


def get_change(changeid):
    """Retrieves ChangeInfo from gerrit using its changeid"""
    get_change_endpoint = (f'{CHROMIUM_REVIEW_BASEURL}/changes/{changeid}/')

    resp = requests.get(get_change_endpoint)
    resp_json = json.loads(resp.text[5:])

    return resp_json


def generate_fix_commit_message(old_changeid):
    """Generates new commit message for a fix change.

    Use script ./contrib/from_upstream.py to generate new commit msg
    Commit message should include essential information:
    i.e:
        FROMGIT, FROMLIST, ANDROID, CHROMIUM, etc.
        commit message indiciating what is happening
        BUG=...
        TEST=...
        tag for Fixes: <upstream-sha>
    """
    old_commit_msg = get_commit(old_changeid)
    print(old_commit_msg)


def create_gerrit_change(reviewers, commit_msg):
    """Uses gerrit api to handle creating gerrit change.

    Determines whether a change for a fix has already been created,
    and avoids duplicate creations.

    May add some additional information to the fix patch for tracking purposes.
    i.e attaching a tag,
    """

    # Call gerrit api to create new change if neccessary
    print('Calling gerrit api', reviewers, commit_msg)
