#!/usr/bin/env python3
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Compare local cherry-picks with upstream SHA1s.

This script compares local and UPSTREAM change by pulling
each into a patch file and compares the two patch files using meld.

You may need to install meld to use this script:
chromeos: emerge dev-vcs/git
debian: sudo apt-get install meld

1) generate list of commit messages that need to be compared. e.g.:
    git log remotes/cros/chromeos-3.18.. > /tmp/git.log

2)  run:  upstream_diff.py /tmp/git.log

3) Close the meld window once you are finished inspecting to see the next one
"""

import re
from subprocess import call
import sys


commit_start = 0
patchid = 1
l_sha = ""

f = open(sys.argv[1], "r")

for line in f.readlines():
    if l_sha != "":
        # first line with leading white space is description
        if l_descr != "":
            if re.match("^    .*$", line):
                l_descr = line.strip()

            if l_descr[0:8] != "UPSTREAM:":
                print("----------------------")
                print("Skipping !UPSTREAM " + l_sha[0:9] + " " + l_descr)
                l_sha = ""
                l_descr = ""
                continue

        if re.match(
            r"^    \(cherry picked from commit ([0-9a-f]+)", line, remote_sha
        ):
            remote_words = line.split()
            remote_sha = remote_words[4].split(")")
            r_sha = remote_sha[0]
            r_sha_file = "%3d" % patchid + "_" + r_sha + ".patch"
            l_sha_file = "%3d" % patchid + "_" + l_sha + ".patch"
            patchid += 1

            print("----------------------")
            print(
                "Comparing "
                + l_sha[0:9]
                + " "
                + l_descr
                + "  AND  "
                + r_sha[0:9]
            )
            print("meld", r_sha_file, l_sha_file)
            call(
                "git format-patch -1 " + l_sha + " --stdout > " + l_sha_file,
                shell=True,
            )
            call(
                "git format-patch -1 " + r_sha + " --stdout > " + r_sha_file,
                shell=True,
            )
            call("meld " + l_sha_file + " " + r_sha_file, shell=True)
            l_sha = ""
            l_descr = ""

    if re.match("^commit *", line):
        if l_sha != "":
            print("No cherry picked SHA1 in " + l_sha[0:9] + " " + l_descr)
        words = line.split()
        l_sha = words[1]
        l_descr = ""
