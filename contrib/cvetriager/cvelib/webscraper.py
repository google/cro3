# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module for collecting CVE data."""

from urllib.parse import urlparse, parse_qs
import os
import string
import logging

from cvelib import logutils
from bs4 import BeautifulSoup
import requests


LOGGER = logutils.setuplogging(loglvl=logging.DEBUG, name='WebScraper')

CVE_URL = 'https://cve.mitre.org/cgi-bin/cvename.cgi'
KERNEL_ORG = 'git.kernel.org'
KERNEL_PATH = ['/cgit/linux/kernel/git/torvalds', '/pub/scm/linux/kernel/git/torvalds/']
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


def is_kernel_org(netloc, path):
    """Check if is useful git.kernel.org link."""
    if netloc != KERNEL_ORG:
        return False

    for link_path in KERNEL_PATH:
        if path.startswith(link_path):
            return True

    return False


def is_github_com(netloc, path):
    """Check if is useful github.com link."""
    return netloc == GITHUB_COM and path.startswith(GITHUB_PATH)


def find_cve_description(cve_html):
    """Returns given CVE's description."""
    soup = BeautifulSoup(cve_html, 'html.parser')

    tag = soup.find('div', attrs={'id': 'GeneratedTable'})

    for t in tag.descendants:
        if t.name == 'th' and t.text == 'Description':
            description = t.parent.find_next_sibling().get_text()

    return description.replace('\n', '')


def find_commit_links(cve_html):
    """Returns commit links from given CVE's webpage."""
    # TODO: Additional pattern to look for might be:
    # https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2019-19076
    commits = []
    soup = BeautifulSoup(cve_html, 'html.parser')

    # Searches through link tags.
    tag = soup.find('div', attrs={'id': 'GeneratedTable'})
    for l in tag.descendants:
        if l.name == 'a':
            link = l.get('href')
            parsed_link = urlparse(link)
            netloc, path = parsed_link.netloc, parsed_link.path

            if is_kernel_org(netloc, path):
                commits.append(link)

            elif is_github_com(netloc, path):
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

    if is_kernel_org(netloc, path):
        try:
            sha = parse_qs(parsed_link.query)['id'][0]
        except KeyError:
            LOGGER.error(f'Sha not found in {link}')

    elif is_github_com(netloc, path):
        sha = os.path.basename(path)

    return sha if is_valid(sha) else None


def find_relevant_commits(cve_number):
    """Looks for the fix commit(s) given the CVE."""
    commits = set()

    req = make_cve_request(cve_number)

    cve_description = find_cve_description(req.text)
    LOGGER.info(f'CVE Description: {cve_description}')

    commit_links = find_commit_links(req.text)

    # Collects fix commit sha(s) from links.
    for link in commit_links:
        LOGGER.debug(f'Looking for sha in {link}')

        sha = find_sha_from_link(link)
        if sha:
            commits.add(sha)

    return commits
