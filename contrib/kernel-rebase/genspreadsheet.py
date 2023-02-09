#!/usr/bin/env python3
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Use information in rebase database to create rebase spreadsheet

Required python modules:
    google-api-python-client google-auth-httplib2 google-auth-oauthlib

The Google Sheets API needs to be enabled to run this script.
Also, you'll need to generate access credentials and store those
in credentials.json.

Disable pyline noise
pylint: disable=no-absolute-import
"""

from __future__ import print_function

import sqlite3

from common import rebase_baseline
from common import rebase_target_tag
from common import rebase_target_version
from common import rebasedb
from common import upstreamdb
import genlib


rebase_filename = "rebase-spreadsheet.id"

other_topic_id = 0  # Sheet Id to be used for "other" topic

red = {"red": 1, "green": 0.4, "blue": 0}
yellow = {"red": 1, "green": 1, "blue": 0}
orange = {"red": 1, "green": 0.6, "blue": 0}
green = {"red": 0, "green": 0.9, "blue": 0}
blue = {"red": 0.3, "green": 0.6, "blue": 1}
white = {"red": 1, "green": 1, "blue": 1}


def get_other_topic_id():
    """Calculate other_topic_id"""

    global other_topic_id  # pylint: disable=global-statement

    conn = sqlite3.connect(rebasedb)
    c = conn.cursor()

    c.execute("select topic, name from topics order by name")
    for topic, name in c.fetchall():
        if name == "other":
            other_topic_id = topic
            break
        if topic >= other_topic_id:
            other_topic_id = topic + 1

    conn.close()
    return other_topic_id


def add_topics_summary(requests):
    """Add topics to summary sheet"""

    conn = sqlite3.connect(rebasedb)
    c = conn.cursor()
    c2 = conn.cursor()
    version = rebase_target_version()
    counted_rows = 0
    counted_effrows = 0

    c.execute("select topic, name from topics order by name")
    rowindex = 1
    for (topic, name) in c.fetchall():
        # Insert 'other' topic last, and don't count it here.
        if name == "other":
            continue
        # Only add summary entry if there are commits touching this topic
        c2.execute(
            "select disposition, reason from commits where topic=%d" % topic
        )
        rows = 0
        effrows = 0
        for (d, r) in c2.fetchall():
            # Skip entries associated with a topic if they are fully upstream
            # and are not being replaced.
            if d == "drop" and r == "upstream":
                continue
            rows += 1
            if d == "pick":
                effrows += 1
        counted_rows += rows
        counted_effrows += effrows
        requests.append(
            {
                "pasteData": {
                    "data": '=HYPERLINK("#gid=%d","%s");%d;%d;;;;chromeos-%s-%s'
                    % (
                        topic,
                        name,
                        rows,
                        effrows,
                        version,
                        name.replace("/", "-"),
                    ),
                    "type": "PASTE_NORMAL",
                    "delimiter": ";",
                    "coordinate": {"sheetId": 0, "rowIndex": rowindex},
                }
            }
        )
        rowindex += 1

    allrows = 0
    alleff = 0
    c2.execute("select disposition, reason from commits where topic != 0")
    for (d, r) in c2.fetchall():
        if d == "drop" and r == "upstream":
            continue
        allrows += 1
        if d != "drop":
            alleff += 1

    # Now create an 'other' topic. We'll use it for unnamed topics.
    requests.append(
        {
            "pasteData": {
                "data": '=HYPERLINK("#gid=%d","other");%d;%d;;;;chromeos-%s-other'
                % (
                    other_topic_id,
                    allrows - counted_rows,
                    alleff - counted_effrows,
                    version,
                ),
                "type": "PASTE_NORMAL",
                "delimiter": ";",
                "coordinate": {"sheetId": 0, "rowIndex": rowindex},
            }
        }
    )

    conn.close()


def create_summary(requests):
    """Create summary sheet"""

    requests.append(
        {
            "updateSheetProperties": {
                # 'sheetId': 0,
                "properties": {
                    "title": "Summary",
                },
                "fields": "title",
            }
        }
    )

    header = (
        "Topic, Entries, Effective Entries, Owner, Reviewer, Status, "
        "Topic branch, Comments"
    )
    genlib.add_sheet_header(requests, 0, header)

    # Now add all topics
    add_topics_summary(requests)


def add_description(requests):
    """Add describing text to 'Summary' sheet"""

    requests.append(
        {
            "appendCells": {
                "sheetId": 0,
                "rows": [
                    {},
                    {
                        "values": [
                            {
                                "userEnteredValue": {
                                    "stringValue": "Topic branch markers:"
                                },
                            },
                        ]
                    },
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": "blue"},
                                "userEnteredFormat": {"backgroundColor": blue},
                            },
                            {
                                "userEnteredValue": {
                                    "stringValue": "branch dropped: All patches upstream, no longer applicable, moved to another topic, or no longer needed"  # pylint: disable=line-too-long
                                },
                            },
                        ]
                    },
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": "green"},
                                "userEnteredFormat": {"backgroundColor": green},
                            },
                            {
                                "userEnteredValue": {
                                    "stringValue": "clean (no or minor conflicts)"
                                },
                            },
                        ]
                    },
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": "yellow"},
                                "userEnteredFormat": {
                                    "backgroundColor": yellow
                                },
                            },
                            {
                                "userEnteredValue": {
                                    "stringValue": "mostly clean; problematic patches marked yellow"
                                },
                            },
                        ]
                    },
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": "orange"},
                                "userEnteredFormat": {
                                    "backgroundColor": orange
                                },
                            },
                            {
                                "userEnteredValue": {
                                    "stringValue": "some problems; problematic patches marked orange"
                                },
                            },
                        ]
                    },
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": "red"},
                                "userEnteredFormat": {"backgroundColor": red},
                            },
                            {
                                "userEnteredValue": {
                                    "stringValue": "severe problems"
                                },
                            },
                        ]
                    },
                ],
                "fields": "*",
            }
        }
    )


def addsheet(requests, index, topic, name):
    """Add sheet with header"""

    print('Adding sheet id=%d index=%d title="%s"' % (topic, index, name))

    requests.append(
        {
            "addSheet": {
                "properties": {
                    "sheetId": topic,
                    "index": index,
                    "title": name,
                }
            }
        }
    )

    # Generate header row
    genlib.add_sheet_header(
        requests, topic, "SHA, Description, Disposition, Contact, Comments"
    )


def add_topics_sheets(requests):
    """Add topics sheets"""

    conn = sqlite3.connect(rebasedb)
    c = conn.cursor()

    c.execute("select topic, name from topics order by name")

    index = 1
    for (topic, name) in c.fetchall():
        # Insert 'other' topic at very end
        if name != "other":
            addsheet(requests, index, topic, name)
            index += 1

    # Add 'other' topic sheet at the very end
    addsheet(requests, index, other_topic_id, "other")
    conn.close()


def add_sha(
    requests,
    sheetId,
    sha,
    contact,
    email,
    subject,
    disposition,
    reason,
    dsha,
    origin,
):
    """Add sha to topics sheet"""

    comment = ""
    color = white

    contact_format = "stringValue"
    if (
        "@google.com" in email
        or "@chromium.org" in email
        or "@collabora.com" in email
    ):
        contact = '=HYPERLINK("mailto:%s","%s")' % (email, contact)
        contact_format = "formulaValue"

    if disposition == "pick" and reason == "revisit":
        if dsha:
            comment = "revisit (similarities with %s commit %s)" % (
                origin,
                dsha,
            )
        else:
            comment = "revisit (imperfect match)"
        color = orange
    elif disposition == "replace" and dsha:
        comment = "with %s commit %s" % (origin, dsha)
        color = yellow
        if reason == "revisit":
            comment += " (revisit: imperfect match)"
            color = orange
    elif disposition == "drop":
        color = yellow
        if reason == "revisit":
            color = red
            if dsha:
                comment = "revisit (imperfect match with %s commit %s)" % (
                    origin,
                    dsha,
                )
            else:
                comment = "revisit (imperfect match)"
        elif reason == "upstream/fixup":
            comment = "fixup of upstream patch %s" % dsha
        elif reason == "upstream/match":
            comment = "%s commit %s" % (origin, dsha)
        elif reason == "revisit/fixup":
            comment = "fixup of %s commit %s" % (origin, dsha)
        elif reason == "reverted":
            comment = reason
            if dsha:
                comment += " (commit %s)" % dsha
        elif reason == "fixup/reverted":
            comment = "fixup of reverted commit %s" % dsha
        else:
            comment = reason
            if dsha:
                comment += " (%s commit %s)" % (origin, dsha)

    print("Adding sha %s (%s) to sheet ID %d" % (sha, subject, sheetId))

    requests.append(
        {
            "appendCells": {
                "sheetId": sheetId,
                "rows": [
                    {
                        "values": [
                            {
                                "userEnteredValue": {"stringValue": sha},
                                "userEnteredFormat": {"backgroundColor": color},
                            },
                            {
                                "userEnteredValue": {"stringValue": subject},
                                "userEnteredFormat": {"backgroundColor": color},
                            },
                            {
                                "userEnteredValue": {
                                    "stringValue": disposition
                                },
                                "userEnteredFormat": {"backgroundColor": color},
                            },
                            {
                                "userEnteredValue": {contact_format: contact},
                                "userEnteredFormat": {"backgroundColor": color},
                            },
                            {
                                "userEnteredValue": {"stringValue": comment},
                                "userEnteredFormat": {"backgroundColor": color},
                            },
                        ]
                    }
                ],
                "fields": "*",
            }
        }
    )


def add_commits(requests):
    """Add commits to sheets"""

    conn = sqlite3.connect(rebasedb)
    uconn = sqlite3.connect(upstreamdb)
    c = conn.cursor()
    c2 = conn.cursor()
    cu = uconn.cursor()

    sheets = set([])

    c.execute(
        "select sha, dsha, contact, email, subject, disposition, reason, topic \
            from commits where topic > 0"
    )
    for (
        sha,
        dsha,
        contact,
        email,
        subject,
        disposition,
        reason,
        topic,
    ) in c.fetchall():
        # Skip entries associated with a topic if they are fully upstream
        # and are not being replaced.
        if disposition == "drop" and reason == "upstream":
            continue
        c2.execute("select topic, name from topics where topic=%d" % topic)
        if c2.fetchone():
            sheetId = topic
        else:
            sheetId = other_topic_id

        cu.execute("select sha from commits where sha='%s'" % dsha)
        if cu.fetchone():
            origin = "upstream"
        else:
            origin = "linux-next"
        sheets.add(sheetId)
        add_sha(
            requests,
            sheetId,
            sha,
            contact,
            email,
            subject,
            disposition,
            reason,
            dsha,
            origin,
        )

    for s in sheets:
        genlib.resize_sheet(requests, s, 0, 5)


def main():
    """Main function"""

    sheet = genlib.init_spreadsheet(
        rebase_filename,
        "Rebase %s -> %s" % (rebase_baseline(), rebase_target_tag()),
    )
    get_other_topic_id()

    requests = []
    create_summary(requests)
    add_topics_sheets(requests)
    genlib.doit(sheet, requests)
    requests = []
    add_commits(requests)
    # Now auto-resize columns A, B, C, and G in Summary sheet
    genlib.resize_sheet(requests, 0, 0, 3)
    genlib.resize_sheet(requests, 0, 6, 7)
    # Add description after resizing
    add_description(requests)
    genlib.doit(sheet, requests)


if __name__ == "__main__":
    main()
