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
import os
import re
import requests

import common
import git_interface


def get_auth_cookie():
    """Load cookies in order to authenticate requests with gerrit/googlesource."""
    # This cookie should exist in order to perform GAIA authenticated requests
    try:
        gerrit_credentials_cookies = \
                http.cookiejar.MozillaCookieJar(common.GCE_GIT_COOKIE_PATH, None, None)
        gerrit_credentials_cookies.load()
        return gerrit_credentials_cookies
    except FileNotFoundError:
        try:
            gerrit_credentials_cookies = \
                    http.cookiejar.MozillaCookieJar(common.LOCAL_GIT_COOKIE_PATH, None, None)
            gerrit_credentials_cookies.load()
            return gerrit_credentials_cookies
        except FileNotFoundError:
            print('Could not locate gitcookies file. Generate cookie file and try again')
            print('If running locally, ensure gitcookies file is located at ~/.gitcookies')
            print('Learn more by visiting go/gob-dev#testing-user-authentication')
            raise


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


def set_and_parse_endpoint(endpoint_url, payload=None):
    """POST request to gerrit endpoint with specified payload."""
    try:
        resp = requests.post(endpoint_url, json=payload, cookies=get_auth_cookie())
        resp.raise_for_status()
        resp_json = json.loads(resp.text[5:])
    except json.decoder.JSONDecodeError as e:
        raise ValueError('Response should contain json )]} prefix to prevent XSSI attacks') from e

    return resp_json


def get_full_changeid(changeid, branch):
    """Returns the changeid with url-encoding in project~branch~changeid format."""
    project = 'chromiumos%2Fthird_party%2Fkernel'
    chromeos_branch = common.chromeos_branch(branch)
    return '{project}~{branch}~{changeid}'.format(project=project,
                                                    branch=chromeos_branch,
                                                    changeid=changeid)


def get_reviewers(changeid, branch):
    """Retrieves list of reviewer emails from gerrit given a chromeos changeid."""
    unique_changeid = get_full_changeid(changeid, branch)
    list_reviewers_endpoint = os.path.join(common.CHROMIUM_REVIEW_BASEURL, 'changes',
                                        unique_changeid, 'reviewers')

    resp = retrieve_and_parse_endpoint(list_reviewers_endpoint)

    try:
        return [reviewer_resp['email'] for reviewer_resp in resp]
    except KeyError as e:
        raise type(e)('Gerrit API endpoint to list reviewers should contain key email') from e


def abandon_change(changeid, branch, reason=None):
    """Abandons a change."""
    unique_changeid = get_full_changeid(changeid, branch)
    abandon_change_endpoint = os.path.join(common.CHROMIUM_REVIEW_BASEURL, 'changes',
                                            unique_changeid, 'abandon')

    abandon_payload = {'message': reason} if reason else None

    try:
        set_and_parse_endpoint(abandon_change_endpoint, abandon_payload)
        print('Abandoned changeid %s on Gerrit' % changeid)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == http.HTTPStatus.CONFLICT:
            print('Change %s has already been abandoned' % changeid)
        else:
            raise


def restore_change(changeid, branch, reason=None):
    """Restores an abandoned change."""
    unique_changeid = get_full_changeid(changeid, branch)
    restore_change_endpoint = os.path.join(common.CHROMIUM_REVIEW_BASEURL, 'changes',
                                            unique_changeid, 'restore')

    restore_payload = {'message': reason} if reason else None

    try:
        set_and_parse_endpoint(restore_change_endpoint, restore_payload)
        print('Restored changeid %s on Gerrit' % changeid)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == http.HTTPStatus.CONFLICT:
            print('Change %s has already been restored' % changeid)
        else:
            raise


def get_change(changeid, branch):
    """Retrieves ChangeInfo from gerrit using its changeid"""
    unique_changeid = get_full_changeid(changeid, branch)
    get_change_endpoint = os.path.join(common.CHROMIUM_REVIEW_BASEURL, 'changes',
                                        unique_changeid)
    return retrieve_and_parse_endpoint(get_change_endpoint)


def set_hashtag(changeid, branch):
    """Set hashtag to be autogenerated indicating a robot generated CL."""
    unique_changeid = get_full_changeid(changeid, branch)
    set_hashtag_endpoint = os.path.join(common.CHROMIUM_REVIEW_BASEURL, 'changes',
                                        unique_changeid, 'hashtags')
    hashtag_input_payload = {'add' : ['autogenerated']}
    set_and_parse_endpoint(set_hashtag_endpoint, hashtag_input_payload)

def get_status(changeid, branch):
    """Retrieves the latest status of a changeid by checking gerrit."""
    change_info = get_change(changeid, branch)
    return change_info['status']

def get_bug_test_line(chrome_sha):
    """Retrieve BUG and TEST lines from the chrome sha."""
    # stable fixes don't have a fixee changeid
    bug_test_line = 'BUG=%s\nTEST=%s'
    bug = test = None
    if not chrome_sha:
        return bug_test_line % (bug, test)

    chrome_commit_msg = git_interface.get_chrome_commit_message(chrome_sha)

    bug_matches = re.findall('^BUG=(.*)$', chrome_commit_msg, re.M)
    test_matches = re.findall('^TEST=(.*)$', chrome_commit_msg, re.M)

    bug = bug_matches[0] if bug_matches else None
    test = test_matches[0] if test_matches else None

    return bug_test_line % (bug, test)


def generate_fix_message(fixer_upstream_sha, bug_test_line):
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
    fix_upstream_commit_msg = git_interface.get_upstream_commit_message(fixer_upstream_sha)

    upstream_full_sha = git_interface.get_upstream_fullsha(fixer_upstream_sha)
    cherry_picked = '(cherry picked from commit %s)\n\n'% upstream_full_sha


    commit_message = ('UPSTREAM: {fix_commit_msg}'
                      '{cherry_picked}'
                      '{bug_test_line}').format(fix_commit_msg=fix_upstream_commit_msg,
                        cherry_picked=cherry_picked, bug_test_line=bug_test_line)

    return commit_message


# Note: Stable patches won't have a fixee_change_id since they come into chromeos as merges
def create_change(fixee_kernel_sha, fixer_upstream_sha, branch):
    """Creates a Patch in gerrit given a ChangeInput object.

    Determines whether a change for a fix has already been created,
    and avoids duplicate creations.
    """
    cwd = os.getcwd()
    chromeos_branch = common.chromeos_branch(branch)

    # fixee_changeid will be None for stable fixee_kernel_sha's
    fixee_changeid = git_interface.get_commit_changeid_linux_chrome(fixee_kernel_sha)

    # if fixee_changeid is set, the fixee_kernel_sha represents a chrome sha
    chrome_kernel_sha = fixee_kernel_sha if fixee_changeid else None

    bug_test_line = get_bug_test_line(chrome_kernel_sha)
    fix_commit_message = generate_fix_message(fixer_upstream_sha, bug_test_line)

    # TODO(hirthanan): find relevant mailing list/reviewers
    # For now we will assign it to a default user like Guenter?
    # This is for stable bug fix patches that don't have a direct fixee changeid
    #  since groups of stable commits get merged as one changeid
    reviewers = ['groeck@chromium.org']
    try:
        if fixee_changeid:
            cl_reviewers = get_reviewers(fixee_changeid, branch)
            if cl_reviewers:
                reviewers = cl_reviewers
    except requests.exceptions.HTTPError:
        # There is a Change-Id in the commit log, but Gerrit does not have a
        # matching entry. Fall back to list of e-mails found in tags after
        # the last "cherry picked" message.
        print('Failed to get reviewer(s) from gerrit for Change-Id %s' % fixee_changeid)
        emails = git_interface.get_tag_emails_linux_chrome(fixee_kernel_sha)
        if emails:
            reviewers = emails

    try:
        # Cherry pick changes and generate commit message indicating fix from upstream
        fixer_changeid = git_interface.cherry_pick_and_push_fix(fixer_upstream_sha,
                                                    chromeos_branch, fix_commit_message, reviewers)
    except ValueError:
        # Error cherry-picking and pushing fix patch
        return None

    os.chdir(cwd)
    return fixer_changeid
