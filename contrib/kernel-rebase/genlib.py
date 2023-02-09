# -*- coding: utf-8 -*-"
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

import os
import pickle

from google.auth.transport.requests import (
    Request,  # pylint: disable=import-error, disable=no-name-in-module
)
from google_auth_oauthlib.flow import (
    InstalledAppFlow,  # pylint: disable=import-error
)
from googleapiclient import discovery  # pylint: disable=import-error


SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Spreadsheet functions


def getsheet():
    """Get and return reference to spreadsheet"""

    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            try:  # py2 or token saved with py3
                creds = pickle.load(token)
            except UnicodeDecodeError:  # py3, token saved with py2
                creds = pickle.load(
                    token, encoding="latin-1"
                )  # pylint: disable=unexpected-keyword-arg
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    service = discovery.build("sheets", "v4", credentials=creds)
    # service = discovery.build('sheets', 'v4', developerKey=API_KEY)
    return service.spreadsheets()  # pylint: disable=no-member


def init_spreadsheet(filename, title):
    """Initialize spreadsheet"""

    sheet = getsheet()
    if filename is None:
        ssid = create_spreadsheet(sheet, title)
    else:
        try:
            with open(filename, "r") as f:
                ssid = f.read().strip("\n")
            request = sheet.get(
                spreadsheetId=ssid, ranges=[], includeGridData=False
            )
            response = request.execute()
            sheets = response.get("sheets")
            delete_sheets((sheet, ssid), sheets)
        except IOError:
            ssid = create_spreadsheet(sheet, title)
            with open(filename, "w") as f:
                f.write(ssid)

    return (sheet, ssid)


# Generic topic functions


def get_other_topic_id(c):
    """Calculate and return other_topic_id"""

    other_topic_id = 0

    c.execute("select topic, name from topics order by name")
    for topic, name in c.fetchall():
        if name == "other":
            return topic
        if topic >= other_topic_id:
            other_topic_id = topic + 1

    return other_topic_id


def get_topic_name(c, topic):
    """Get topic name from topic id"""

    c.execute("select name from topics where topic is '%s'" % topic)
    topic = c.fetchone()
    if topic:
        return topic[0]

    return None


# Spreadsheet manipulation functions


def doit(sheet, requests):
    """Execute a request"""

    body = {"requests": requests}

    request = sheet[0].batchUpdate(spreadsheetId=sheet[1], body=body)
    response = request.execute()
    return response


def hide_sheet(sheet, sheetId, hide):
    """Move 'Data' sheet to end of spreadsheet."""
    request = []

    request.append(
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheetId,
                    "hidden": hide,
                },
                "fields": "hidden",
            }
        }
    )

    doit(sheet, request)


def create_spreadsheet(sheet, title):
    """Create a spreadsheet and return reference to it"""
    spreadsheet = {"properties": {"title": title, "locale": "en_US"}}

    request = sheet.create(body=spreadsheet, fields="spreadsheetId")
    response = request.execute()

    return response.get("spreadsheetId")


def delete_sheets(sheet, sheets):
    """Delete all sheets except sheet 0. In sheet 0, delete all values."""
    # Unhide 'Data' sheet. If it is hidden we can't remove the other sheets.
    hide_sheet(sheet, 0, False)
    request = []
    for s in sheets:
        sheetId = s["properties"]["sheetId"]
        if sheetId != 0:
            request.append({"deleteSheet": {"sheetId": sheetId}})
        else:
            rows = s["properties"]["gridProperties"]["rowCount"]
            request.append(
                {
                    "deleteRange": {
                        "range": {
                            "sheetId": sheetId,
                            "startRowIndex": 0,
                            "endRowIndex": rows,
                        },
                        "shiftDimension": "ROWS",
                    }
                }
            )

    # We are letting this fail if there was nothing to clean. This will
    # hopefully result in re-creating the spreadsheet.
    doit(sheet, request)


def resize_sheet(requests, sheetId, start, end):
    """Resize a sheet in provided range"""

    requests.append(
        {
            "autoResizeDimensions": {
                "dimensions": {
                    "sheetId": sheetId,
                    "dimension": "COLUMNS",
                    "startIndex": start,
                    "endIndex": end,
                }
            }
        }
    )


def add_sheet_header(requests, sheetId, fields):
    """Add provided header line to specified sheet.

    Make it bold.

    Args:
        requests: Reference to list of requests to send to API.
        sheetId: Sheet Id
        fields: string with comma-separated list of fields
    """
    # Generate header row
    requests.append(
        {
            "pasteData": {
                "data": fields,
                "type": "PASTE_NORMAL",
                "delimiter": ",",
                "coordinate": {"sheetId": sheetId, "rowIndex": 0},
            }
        }
    )

    # Convert header row to bold and centered
    requests.append(
        {
            "repeatCell": {
                "range": {
                    "sheetId": sheetId,
                    "startRowIndex": 0,
                    "endRowIndex": 1,
                },
                "cell": {
                    "userEnteredFormat": {
                        "horizontalAlignment": "CENTER",
                        "textFormat": {"bold": True},
                    }
                },
                "fields": "userEnteredFormat(textFormat,horizontalAlignment)",
            }
        }
    )


def move_sheet(sheet, sheetId, to):
    """Move sheet to end of spreadsheet."""

    request = []

    request.append(
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheetId,
                    "index": to,
                },
                "fields": "index",
            }
        }
    )

    doit(sheet, request)


def sort_sheet(request, sheetId, sortby, order, rows, columns):
    """Sort sheet in given order, starting with row 1, all rows and columns as provided."""

    request.append(
        {
            "sortRange": {
                "range": {
                    "sheetId": sheetId,
                    "startRowIndex": 1,
                    "endRowIndex": rows,
                    "startColumnIndex": 0,
                    "endColumnIndex": columns,
                },
                "sortSpecs": [{"dimensionIndex": sortby, "sortOrder": order}],
            }
        }
    )


def source_range(sheetId, rows, column):
    """Return source range"""

    return {
        "sourceRange": {
            "sources": [
                {
                    "sheetId": sheetId,
                    "startRowIndex": 0,
                    "endRowIndex": rows,
                    "startColumnIndex": column,
                    "endColumnIndex": column + 1,
                }
            ]
        }
    }


def scope(name, sheetId, rows, column):
    """Return single source range"""

    return {name: source_range(sheetId, rows, column)}


def sscope(name, sheetId, rows, start, end):
    """Return multiple source ranges"""

    s = [scope(name, sheetId, rows, start)]
    while start < end:
        start += 1
        s += [scope(name, sheetId, rows, start)]
    return s
