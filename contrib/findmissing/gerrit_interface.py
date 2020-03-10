#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing methods interfacing with gerrit.

i.e Create new bugfix change tickets, and reading metadata about a specific change.

Example CURL command that creates CL:
curl -b /home/chromeos_patches/.git-credential-cache/cookie \
        --header "Content-Type: application/json" \
        --data \
        '{"project":"chromiumos/third_party/kernel",\
        "subject":"test",\
        "branch":"chromeos-4.19",\
        "topic":"test_topic"}' https://chromium-review.googlesource.com/a/changes/
"""

from __future__ import print_function
import json
import http
import requests

from common import CHROMIUM_REVIEW_BASEURL, GIT_COOKIE_PATH


def get_auth_cookie():
    """Load cookies in order to authenticate requests with gerrit/googlesource."""
    # This cookie should exist on GCE in order to perform GAIA authenticated requests
    gerrit_credentials_cookies = http.cookiejar.MozillaCookieJar(GIT_COOKIE_PATH, None, None)
    gerrit_credentials_cookies.load()
    return gerrit_credentials_cookies

def retrieve_and_parse_endpoint(endpoint_url):
    """Retrieves Gerrit endpoint response and removes XSSI prefix )]}'"""
    resp = requests.get(endpoint_url, cookies=get_auth_cookie())

    try:
        resp_json = json.loads(resp.text[5:])
    except json.decoder.JSONDecodeError as e:
        raise ValueError('Response should contain json )]} prefix to prevent XSSI attacks', e)

    return resp_json


def get_commit(changeid):
    """Retrieves current commit message for a change.

    May add some additional information to the fix patch for tracking purposes.
    i.e attaching a tag
    """
    get_commit_endpoint = '%s/changes/%s/revisions/current/commit/' % (
            CHROMIUM_REVIEW_BASEURL, changeid)
    return retrieve_and_parse_endpoint(get_commit_endpoint)


def get_reviewers(changeid):
    """Retrieves list of reviewers from gerrit given a chromeos changeid."""
    list_reviewers_endpoint = '%s/changes/%s/reviewers/' % (CHROMIUM_REVIEW_BASEURL, changeid)
    return retrieve_and_parse_endpoint(list_reviewers_endpoint)


def get_change(changeid):
    """Retrieves ChangeInfo from gerrit using its changeid"""
    get_change_endpoint = '%s/changes/%s/' % (CHROMIUM_REVIEW_BASEURL, changeid)
    return retrieve_and_parse_endpoint(get_change_endpoint)


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
