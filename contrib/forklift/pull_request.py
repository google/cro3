# -*- coding: utf-8 -*-
#
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Represents a pull request sent upstream"""

import mailbox
import re

import requests


class PullRequest:
    """Represents a pull request sent upstream

    Attributes:
        base_commit: The common ancestor commit this pull request is based upon
        end_commit: The remote commit at which this pull request ends
        source_tree: The location of the remote tree to fetch this pull from
        source_ref: The refspec from the remote to find the pull
    """

    def __init__(self, mailing_list, msg_id, local_pull):
        """Inits PullRequest class with given list/msgid.

        Args:
            mailing_list: The name of the mailing list to use on lore.
            msg_id: The Message-Id of the pull request e-mail.
            local_pull: The path to a local pull request.
        """
        if mailing_list and msg_id:
            url = f"https://lore.kernel.org/{mailing_list}/{msg_id}/raw"
            req = requests.get(url)
            req.raise_for_status()
            msg = mailbox.mboxMessage(req.text)
            charset = msg.get_param("charset")
            if not charset:
                charset = "us-ascii"
            self._pull_request = msg.get_payload(decode=True).decode(charset)

        elif local_pull:
            with open(local_pull, "r") as f:
                self._pull_request = f.read()
        else:
            raise ValueError("Invalid pull request source!")

        self._parse_pull_request()

    def _parse_pull_request(self):
        """Extract the remote and ref info from the text of the pull request."""
        m = re.findall(
            r"The following changes since commit ([a-f0-9]+):",
            self._pull_request,
        )
        if not m:
            raise ValueError("Failed to find base commit in pull request")
        elif len(m) != 1:
            raise ValueError(f"Invalid number of base commits found ({len(m)})")

        self.base_commit = m[0]

        m = re.findall(
            r"available in the Git repository at:\s+(\S+)\s(\S+)\n",
            self._pull_request,
            re.MULTILINE,
        )
        if not m:
            raise ValueError("Failed to find source tree in pull request")
        elif len(m) != 1:
            raise ValueError(f"Invalid number of source trees found ({len(m)})")

        self.source_tree = m[0][0]
        self.source_ref = m[0][1]

        m = re.findall(
            r"for you to fetch changes up to ([a-f0-9]+):", self._pull_request
        )
        if not m:
            raise ValueError("Failed to find end commit in pull request")
        elif len(m) != 1:
            raise ValueError(f"Invalid number of end commits found ({len(m)})")

        self.end_commit = m[0]
