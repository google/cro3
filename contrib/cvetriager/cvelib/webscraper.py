# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module for collecting CVE data."""

from urllib.parse import urlparse, parse_qs
import os
import string

from bs4 import BeautifulSoup
import requests


CVE_URL = 'https://cve.mitre.org/cgi-bin/cvename.cgi'
KERNEL_ORG = 'git.kernel.org'
KERNEL_PATH = '/cgit/linux/kernel/git/torvalds'
GITHUB_COM = 'github.com'
GITHUB_PATH = '/torvalds/linux/'


class WebScraperException(Exception):
    """Exception class for web scraper."""


def make_cve_request(cve_number):
    """Generates CVE url."""
    cve = {'name': cve_number}
    r = requests.get(CVE_URL, params=cve)

    if r.status_code != 200:
        raise WebScraperException('Status code is not 200 OK.')

    # Checks page for an invalid CVE number. This is only done because the page
    # is still existent even if the CVE number is not, therefore it returns a
    # 200 status code and passes the first check.
    soup = BeautifulSoup(r.text, 'html.parser')
    tag = soup.find('div', attrs={'id':'CenterPane'})

    for d in tag.descendants:
        if d.name == 'h2' and d.string.startswith('ERROR:'):
            raise WebScraperException('CVE number is invalid.')

    return r


def find_commit_links(cve_html):
    """Returns commit links from given CVE's webpage."""
    commits = []
    soup = BeautifulSoup(cve_html, 'html.parser')

    # Searches through link tags.
    tag = soup.find('div', attrs={'id': 'GeneratedTable'})
    for l in tag.descendants:
        if l.name == 'a':
            link = l.get('href')
            parsed_link = urlparse(link)
            netloc, path = parsed_link.netloc, parsed_link.path

            if netloc == KERNEL_ORG and path.startswith(KERNEL_PATH):
                commits.append(link)

            elif netloc == GITHUB_COM and path.startswith(GITHUB_PATH):
                commits.append(link)

    return commits


def is_valid(sha):
    """Returns True if sha is a hexidecimal string."""
    if not sha:
        return False
    return set(sha).issubset(string.hexdigits)


def find_sha_from_link(link):
    """Returns sha, if it exists, based on link given."""
    parsed_link = urlparse(link)
    netloc, path = parsed_link.netloc, parsed_link.path

    sha = None

    if netloc == KERNEL_ORG and path.startswith(KERNEL_PATH):
        try:
            sha = parse_qs(parsed_link.query)['id'][0]
        except KeyError:
            pass

    elif netloc == GITHUB_COM and path.startswith(GITHUB_PATH):
        sha = os.path.basename(path)

    return sha if is_valid(sha) else None


def find_relevant_commits(cve_number):
    """Looks for the fix commit(s) given the CVE."""
    commits = set()

    req = make_cve_request(cve_number)
    commit_links = find_commit_links(req.text)

    # Collects fix commit sha(s) from links.
    for link in commit_links:
        sha = find_sha_from_link(link)
        if sha:
            commits.add(sha)

    return commits
