# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Testing script for cvelib/webscraper.py."""

import unittest
from urllib.parse import urlparse

from cvelib import webscraper


class TestWebScraper(unittest.TestCase):
    """Test class for cvelib/webscraper.py."""

    # CVE number used for test cases.
    CVE_NUMBER = "CVE-2017-18017"

    # Expected fix commit from CVE_NUMBER.
    SHA = "2638fd0f92d4397884fd991d8f4925cb3f081901"

    # Expected commit links taken from CVE_NUMBER.
    LINKS = [
        f"http://git.kernel.org/cgit/linux/kernel/git/torvalds/linux.git/commit/?id={SHA}",
        f"https://github.com/torvalds/linux/commit/{SHA}",
    ]

    CVE_DESCRIPTION = (
        "The tcpmss_mangle_packet function in net/netfilter/xt_TCPMSS.c in the Linux kernel before "
        "4.11, and 4.9.x before 4.9.36, allows remote attackers to cause a denial of service "
        "(use-after-free and memory corruption) or possibly have unspecified other impact by "
        "leveraging the presence of xt_TCPMSS in an iptables action."
    )

    def test_make_cve_request(self):
        """Tests that url request was made."""
        req = webscraper.make_cve_request(TestWebScraper.CVE_NUMBER)

        expected = (
            "https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2017-18017"
        )

        # Check if proper url was fetched.
        self.assertEqual(req.url, expected)

    def test_find_cve_description(self):
        """Tests that CVE description was returned."""
        req = webscraper.make_cve_request(TestWebScraper.CVE_NUMBER)

        description = webscraper.find_cve_description(req.text)

        self.assertEqual(description, TestWebScraper.CVE_DESCRIPTION)

    def test_find_commit_links(self):
        """Tests that correct commit links were found."""
        req = webscraper.make_cve_request(TestWebScraper.CVE_NUMBER)

        links = webscraper.find_commit_links(req.text)

        self.assertEqual(links, TestWebScraper.LINKS)

    def test_cve_without_git_links(self):
        """Tests that no link is added if it doesn't have the expected prefixes."""
        # This CVE is expected to contain no git links.
        cve_num = "CVE-2020-9364"

        req = webscraper.make_cve_request(cve_num)

        links = webscraper.find_commit_links(req.text)

        self.assertEqual(len(links), 0)

    def test_find_sha(self):
        """Tests that the correct sha is found from the given link."""
        sha = webscraper.find_sha_from_link(TestWebScraper.LINKS[0])
        self.assertEqual(sha, TestWebScraper.SHA)

        sha2 = webscraper.find_sha_from_link(TestWebScraper.LINKS[1])
        self.assertEqual(sha2, TestWebScraper.SHA)

    def test_find_relevant_commits(self):
        """Tests that correct shas are found from the given CVE."""
        commits = webscraper.find_relevant_commits(TestWebScraper.CVE_NUMBER)

        expected = {TestWebScraper.SHA}

        self.assertEqual(commits, expected)

    def test_cve_without_shas(self):
        """Tests that a CVE with no fix shas returns an empty set."""
        # This CVE is expected to contain no fix shas.
        cve_num = "CVE-2018-20669"

        commits = webscraper.find_relevant_commits(cve_num)

        self.assertEqual(len(commits), 0)

    def test_invalid_cve_num(self):
        """Tests that exception is raised if the cve number is invalid."""
        invalid_cve = "1234"

        self.assertRaises(
            webscraper.WebScraperException,
            webscraper.make_cve_request,
            invalid_cve,
        )

    def test_link_without_sha(self):
        """Tests that links with invalid sha or no sha at all return None."""
        # This link has an expected prefix but no sha present.
        link = (
            "http://git.kernel.org/cgit/linux/kernel/git/torvalds/"
            "linux.git/log/drivers/gpu/drm/i915/i915_gem_execbuffer.c"
        )

        sha = webscraper.find_sha_from_link(link)

        self.assertIsNone(sha)

    def test_non_git_link(self):
        """Tests that a non git link returns None for the sha."""
        link = "google.com"

        sha = webscraper.find_sha_from_link(link)

        self.assertIsNone(sha)

    def test_invalid_sha(self):
        """Tests that sha is not a hexidecimal string."""
        sha = "a123!"
        self.assertFalse(webscraper.is_valid(sha))

        sha = None
        self.assertFalse(webscraper.is_valid(sha))

    def test_valid_sha(self):
        """Tests that the sha found is a hexidecimal string."""
        self.assertTrue(webscraper.is_valid(TestWebScraper.SHA))

    def test_is_kernel_org(self):
        """Unit test for is_kernel_org."""
        parsed_link = urlparse(TestWebScraper.LINKS[0])
        netloc, path = parsed_link.netloc, parsed_link.path

        self.assertTrue(webscraper.is_kernel_org(netloc, path))

        pub_scm_torvalds_link = (
            "https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/"
            "linux.git/commit/?id=f2d67fec0b43edce8c416101cdc52e71145b5fef"
        )

        parsed_link2 = urlparse(pub_scm_torvalds_link)
        netloc2, path2 = parsed_link2.netloc, parsed_link2.path
        self.assertTrue(webscraper.is_kernel_org(netloc2, path2))

    def test_is_github_com(self):
        """Unit test for is_github_com."""
        parsed_link = urlparse(TestWebScraper.LINKS[1])
        netloc, path = parsed_link.netloc, parsed_link.path

        self.assertTrue(webscraper.is_github_com(netloc, path))
