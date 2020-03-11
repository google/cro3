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
import os

from common import CHROMIUM_REVIEW_BASEURL, GIT_COOKIE_PATH


def get_auth_cookie():
    """Load cookies in order to authenticate requests with gerrit/googlesource."""
    # This cookie should exist on GCE in order to perform GAIA authenticated requests
    gerrit_credentials_cookies = http.cookiejar.MozillaCookieJar(GIT_COOKIE_PATH, None, None)
    gerrit_credentials_cookies.load()
    return gerrit_credentials_cookies

def retrieve_and_parse_endpoint(endpoint_url):
    """Retrieves Gerrit endpoint response and removes XSSI prefix )]}'"""
    try:
        resp = requests.get(endpoint_url, cookies=get_auth_cookie())
        resp.raise_for_status()
        resp_json = json.loads(resp.text[5:])
    except requests.exceptions.HTTPError as e:
        raise type(e)('Endpoint %s should have HTTP response 200' % endpoint_url) from e
    except json.decoder.JSONDecodeError as e:
        raise ValueError('Response should contain json )]} prefix to prevent XSSI attacks') from e

    return resp_json

def set_and_parse_endpoint(endpoint_url, payload):
    """POST request to gerrit endpoint with specified payload."""
    try:
        resp = requests.post(endpoint_url, json=payload, cookies=get_auth_cookie())
        resp.raise_for_status()
        resp_json = json.loads(resp.text[5:])
    except requests.exceptions.HTTPError as e:
        raise type(e)('Endpoint %s should have HTTP response 200' % endpoint_url) from e
    except json.decoder.JSONDecodeError as e:
        raise ValueError('Response should contain json )]} prefix to prevent XSSI attacks') from e

    return resp_json

def get_commit(changeid):
    """Retrieves current commit message for a change.

    May add some additional information to the fix patch for tracking purposes.
    i.e attaching a tag
    """
    get_commit_endpoint = os.path.join(CHROMIUM_REVIEW_BASEURL, 'changes',
                                        changeid, 'revisions/current/commit')
    return retrieve_and_parse_endpoint(get_commit_endpoint)


def get_changeid_reviewers(changeid):
    """Retrieves list of reviewer emails from gerrit given a chromeos changeid."""
    list_reviewers_endpoint = os.path.join(CHROMIUM_REVIEW_BASEURL, 'changes',
                                        changeid, 'reviewers')

    resp = retrieve_and_parse_endpoint(list_reviewers_endpoint)

    try:
        return [reviewer_resp['email'] for reviewer_resp in resp]
    except KeyError as e:
        raise type(e)('Gerrit API endpoint to list reviewers should contain key email') from e

def set_changeid_reviewers(changeid, reviewer_emails):
    """Adds reviewers to a Gerrit CL."""
    add_reviewer_endpoint = os.path.join(CHROMIUM_REVIEW_BASEURL, 'changes',
                                        changeid, 'reviewers')

    for email in reviewer_emails:
        payload = {'reviewer': email}
        set_and_parse_endpoint(add_reviewer_endpoint, payload)


def get_change(changeid):
    """Retrieves ChangeInfo from gerrit using its changeid"""
    get_change_endpoint = os.path.join(CHROMIUM_REVIEW_BASEURL, 'changes', changeid)
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
