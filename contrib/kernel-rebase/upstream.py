#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Search upstream commits in rebase database amd mark accordingly"""

from __future__ import print_function

from collections import defaultdict

# requires "pip install fuzzywuzzy"
import operator
import re
import sqlite3
import subprocess
import time

# from common import nextdb
from common import chromeos_path
from common import is_in_target
from common import rebasedb
from common import upstream_path
from common import upstreamdb
from fuzzywuzzy import fuzz  # pylint: disable=import-error
from fuzzywuzzy import process  # pylint: disable=import-error


encoding = "utf-8"

# List of all subjects, split into dictionary indexed by each word
# in the subject.
_alldescs = defaultdict(list)


def NOW():
    """Return current time"""
    return int(time.time())


def get_patch(path, psha):
    """Return patch associated with psha from repository, or None if not found"""

    patch = subprocess.check_output(
        ["git", "-C", path, "show", "--format='%b'", "-U1", psha],
        encoding="utf-8",
        errors="ignore",
    )
    i = re.search("^diff", patch, flags=re.MULTILINE).group()
    if i:
        ind = patch.index(i)
        return patch[ind:]
    return None


def patch_ratio(usha, lsha, ref=upstream_path):
    """compare patches

    Args:
        usha: First SHA to compare
        lsha: Second SHA to compare
        ref: optional repository path name

    Returns:
        Tuple with two different fuzzy matches

    Fuzzy match is applied to first 1,000 lines in each patch
    to avoid stalls. If one of the patches has more than 1,000
    lines, also compare the number of lines in each patch and
    return (0,0) if the mismatch is too significant.
    """

    lpatch = get_patch(ref, usha)
    if lpatch:
        upatch = get_patch(chromeos_path, lsha)
        if upatch:
            llen = lpatch.count("\n")
            ulen = upatch.count("\n")
            # Large patches: more than 20% difference in patch size is a mismatch
            if llen > 2000 or ulen > 2000:
                if abs(llen - ulen) > llen / 5:
                    return (0, 0)
            lpatch = "\n".join(lpatch.splitlines()[:2000])
            upatch = "\n".join(upatch.splitlines()[:2000])
            return (
                fuzz.ratio(upatch, lpatch),
                fuzz.token_set_ratio(upatch, lpatch),
            )
    return (0, 0)


def best_match(s):
    """Find best match for subject in _alldescs.

    Split provided subject into words. Search for subject in each of the
    word lists.

    Args:
        s: The subject to match.

    Returns:
        Best subject match as list (subject, score). If multiple subjects match
        with the same score, return first encountered match with this score.
    """

    matches = []
    s = re.sub(r"[^a-zA-Z0-9_/\s]+", " ", s)
    for word in s.split():
        match = process.extractOne(
            s, _alldescs[word], scorer=fuzz.token_sort_ratio, score_cutoff=65
        )
        if match:
            matches.append(match)
    if not matches:
        return ("", 0)
    best = max(matches, key=operator.itemgetter(1))
    return (best[0], best[1])


def getallsubjects(db=upstreamdb):
    """Split subjects into a dictionary of of word-hashed lists.

    By searching the resulting lists, we can speed up processing
    significantly.

    Returns:
        _alldescs[] is populated.
    """

    global _alldescs  # pylint: disable=global-statement

    _alldescs = defaultdict(list)
    db = sqlite3.connect(db)
    cu = db.cursor()
    cu.execute("select subject from commits")
    for (subject,) in cu.fetchall():
        wlist = re.sub(r"[^a-zA-Z0-9_\s]+", " ", subject)
        words = wlist.split()
        for word in words:
            _alldescs[word].append(subject)
    db.close()


def update_commit(c, sha, disposition, reason, sscore=None, pscore=None):
    """Update a commit entry in the database if the disposition changes"""

    c.execute("select disposition from commits where sha='%s'" % sha)
    disp = c.fetchall()
    if not disp or disp != disposition:
        c.execute(
            "UPDATE commits SET disposition=('%s') where sha='%s'"
            % (disposition, sha)
        )
        c.execute(
            "UPDATE commits SET reason=('%s') where sha='%s'" % (reason, sha)
        )
        if sscore:
            c.execute(
                "UPDATE commits SET sscore=%d where sha='%s'" % (sscore, sha)
            )
        if pscore:
            c.execute(
                "UPDATE commits SET pscore=%d where sha='%s'" % (pscore, sha)
            )
        c.execute(
            "UPDATE commits SET updated=('%d') where sha='%s'" % (NOW(), sha)
        )
    else:
        print("Registered disposition for sha %s: %s" % (sha, disp))
        print(
            "Not updating database for SHA '%s', requested disposition=%s, reason=%s"
            % (sha, disposition, reason)
        )


def doit(db=upstreamdb, path=upstream_path, name="upstream"):
    """Do the actual work.

    Read all commits from database, compare against commits in provided
    database, and mark accordingly.
    """

    rp = re.compile(
        "(CHROMIUM: *|CHROMEOS: *|UPSTREAM: *|FROMGIT: *|FROMLIST: *|BACKPORT: *)+(.*)"
    )
    rpf = re.compile("(FIXUP: *|Fixup: *)(.*)")

    merge = sqlite3.connect(rebasedb)
    c = merge.cursor()
    c2 = merge.cursor()
    db = sqlite3.connect(db)
    cu = db.cursor()

    c.execute("select sha, patchid, subject, disposition from commits")
    for (
        sha,
        patchid,
        desc,
        disposition,
    ) in c.fetchall():  # pylint: disable=too-many-nested-blocks
        if disposition == "drop":
            continue
        # First look for matching upstream patch ID
        cu.execute(
            "SELECT sha, subject from commits where patchid is '%s'" % patchid
        )
        fsha = cu.fetchone()
        if fsha:
            rsha = fsha[0]
            subject = fsha[1]
            c2.execute(
                "UPDATE commits SET dsha=('%s') where sha='%s'" % (rsha, sha)
            )
            in_target = is_in_target(rsha)
            if in_target:
                disposition = "drop"
            else:
                disposition = "replace"
            print(
                "Patch ID match for %s ('%s')" % (sha, desc.replace("'", "''"))
            )
            print(
                "    Matching %s commit %s ('%s'), %s"
                % (name, rsha, subject.replace("'", "''"), disposition)
            )
            update_commit(c2, sha, disposition, "upstream")
            continue

        m = rp.search(desc)
        mf = rpf.search(desc)
        if m:
            # print("Regex match for '%s'" % desc.replace("'", "''"))
            ndesc = m.group(2).replace("'", "''")
            rdesc = m.group(2)
            # print("    Match subject '%s'" % ndesc)
            cu.execute(
                "select sha, subject, integrated from commits "
                "where subject='%s'" % ndesc
            )
            fsha = cu.fetchone()
            if fsha:
                c2.execute(
                    "UPDATE commits SET dsha=('%s') where sha='%s'"
                    % (fsha[0], sha)
                )
                in_target = is_in_target(fsha[2])
                if mf:
                    print(
                        "Regex match for %s '%s'"
                        % (sha, desc.replace("'", "''"))
                    )
                    print("    Match subject '%s'" % ndesc)
                    print("    FIXUP patch")
                    print(
                        "    Found matching %s commit %s ('%s'), drop"
                        % (name, fsha[0], fsha[1].replace("'", "''"))
                    )
                    update_commit(c2, sha, "drop", "%s/fixup" % name, 100)
                    continue
                # print("    Upstream subject for %s matches %s" % (fsha[1], sha))
                # print("    Local subject: %s" % desc)
                # print("    Upstream subject: %s" % ndesc)
                # print("    In v4.9: %d" % fsha[2])
                if in_target:
                    disposition = "drop"
                else:
                    disposition = "replace"

                # This is a perfect match. Set sscore to 100.
                sscore = 100

                (ratio, setratio) = patch_ratio(fsha[0], sha, ref=path)
                pscore = (ratio + setratio) / 2

                # Like many others, 160 is a magic number derived from experiments.
                if ratio + setratio > 160:
                    reason = "%s/match" % name
                else:
                    reason = "revisit"

                update_commit(c2, sha, disposition, reason, sscore, pscore)
            else:
                print("Regex match for '%s'" % desc.replace("'", "''"))
                print("    Match subject '%s'" % ndesc)
                print(
                    "    No match in %s for '%s' [marked %s], trying fuzzy match"
                    % (name, sha, disposition)
                )
                (mdesc, result) = best_match(rdesc)
                if result == 0:
                    print("    No close match")
                    continue
                if result <= 75:
                    print("    Best candidate: %s" % mdesc)
                    print("    Basic subject match %d insufficient" % result)
                    # If the patch is tagged UPSTREAM:, but upstream does not have
                    # a matching subject, something is odd. Need to revisit.
                    if desc.startswith("UPSTREAM:"):
                        c2.execute(
                            "UPDATE commits SET reason=('revisit') where sha='%s'"
                            % sha
                        )
                        c2.execute(
                            "UPDATE commits SET sscore=%d where sha='%s'"
                            % (result, sha)
                        )
                    continue
                # Use default ratio (not fuzz.token_sort_ratio) for further matching.
                result = fuzz.ratio(rdesc, mdesc)
                smatch = fuzz.token_set_ratio(rdesc, mdesc)
                print("    subject match results %d/%d" % (result, smatch))
                c2.execute(
                    "UPDATE commits SET sscore=%d where sha='%s'"
                    % ((result + smatch) / 2, sha)
                )
                cu.execute(
                    "select sha, subject, integrated from commits "
                    "where subject='%s'" % mdesc.replace("'", "''")
                )
                fsha = cu.fetchone()
                if fsha:
                    c2.execute(
                        "UPDATE commits SET dsha=('%s') where sha='%s'"
                        % (fsha[0], sha)
                    )
                    in_target = is_in_target(fsha[2])
                    print(
                        "    Upstream candidate %s ('%s')"
                        % (fsha[0], fsha[1].replace("'", "''"))
                    )
                    if mf:
                        # We have:
                        #        sha is this patch
                        #        fsha[0] is the replacement candidate
                        c2.execute(
                            "select sha from commits where dsha is '%s'"
                            % fsha[0]
                        )
                        dsha = c2.fetchone()
                        if dsha:
                            print(
                                "    FIXUP: Found patch in %s as replacement. dropping"
                            )
                            update_commit(c2, sha, "drop", "revisit/fixup", 100)
                        else:
                            print("    FIXUP: No replacement target. Revisit.")
                            c2.execute(
                                "UPDATE commits SET reason=('revisit') where sha='%s'"
                                % sha
                            )
                        continue
                    (ratio, setratio) = patch_ratio(fsha[0], sha)
                    c2.execute(
                        "UPDATE commits SET pscore=%d where sha='%s'"
                        % ((ratio + setratio) / 2, sha)
                    )
                    if (
                        (result <= 90 or smatch < 98)
                        and smatch != 100
                        and (result <= 95 or smatch <= 95)
                    ):
                        # Compare subject strings after ':'.
                        # If there is a perfect match, look into patch contents after all
                        rdesc2 = re.sub(r"[\S]+:\s*", "", rdesc)
                        mdesc2 = re.sub(r"[\S]+:\s*", "", mdesc)
                        if rdesc2 != mdesc2:
                            print(
                                "    Subject match %d/%d insufficient"
                                % (result, smatch)
                            )
                            c2.execute(
                                "UPDATE commits SET reason=('revisit') where sha='%s'"
                                % sha
                            )
                            continue
                    c2.execute(
                        "select filename from files where sha is '%s'" % sha
                    )
                    lfilenames = c2.fetchall()
                    cu.execute(
                        "select filename from files where sha is '%s'" % fsha[0]
                    )
                    ufilenames = cu.fetchall()
                    scrutiny = 0
                    if lfilenames != ufilenames:
                        print("    File name mismatch, increasing scrutiny")
                        scrutiny = 20
                    print("    patch match results %d/%d" % (ratio, setratio))
                    if (
                        smatch < 100 and (ratio <= 90 or setratio <= 90)
                    ) or ratio <= 70 + scrutiny:
                        print(
                            "    code match %d/%d insufficient"
                            % (ratio, setratio)
                        )
                        print("    Mark sha '%s' for revisit" % sha)
                        c2.execute(
                            "UPDATE commits SET reason=('revisit') where sha='%s'"
                            % sha
                        )
                        continue
                    # We have a match.
                    if in_target:
                        print("    Drop sha '%s' (close match)" % sha)
                        disposition = "drop"
                        reason = "%s/match" % name
                    else:
                        print(
                            "    Replace sha '%s' with '%s' (close match)"
                            % (sha, fsha[0])
                        )
                        disposition = "replace"
                        reason = "revisit"
                    update_commit(c2, sha, disposition, reason)
                else:
                    print(
                        "    NOTICE: missing match in %s for '%s'"
                        % (name, mdesc.replace("'", "''"))
                    )

    merge.commit()
    merge.close()
    db.close()


# First run against upstream (mainline).
getallsubjects()
doit()

# repeat against -next. This will generate a list of patches
# to be replaced with patches found in -next (which are probably
# a better match to future upstream patches). At the very least,
# this gives us an idea how many of the local patches are actually
# queued to the next kernel release.
# TODO: Check upstream/mainline and -next for Fixup: patches
# of patches which are going to be applied, and apply those
# as well.
# FIXME: This never really worked - next_path is not imported.
# We'll also have to update nextdb to match the format of
# upstreamdb if we really want this to work.
# if nextdb:
#     getallsubjects(nextdb)
#     doit(nextdb, next_path, 'next')
