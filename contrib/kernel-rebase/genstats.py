#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Create rebase statistics spreadsheet

Required python modules:
google-api-python-client google-auth-httplib2 google-auth-oauthlib

The Google Sheets API needs to be enabled to run this script.
Also, you'll need to generate access credentials and store those
in credentials.json.
"""

from __future__ import print_function

import sqlite3
import re
import datetime
import time

from config import topiclist_consolidated
from common import rebasedb, nextdb, upstreamdb, rebase_baseline

import genlib

stats_filename = 'rebase-stats.id'

rp = re.compile(
    '(CHROMIUM: *|CHROMEOS: *|UPSTREAM: *|FROMGIT: *|FROMLIST: *|BACKPORT: *)+(.*)'
)

stats_colors = [
    {
        'red': 0,
        'green': 0.8,
        'blue': 0
    },  # Queued: green
    {
        'blue': 1
    },  # Upstream: blue
    {
        'red': 0.5,
        'green': 0.5,
        'blue': 1
    },  # Backport: light blue
    {
        'red': 0.9,
        'green': 0.9
    },  # yellow
    {
        'red': 1,
        'green': 0.6
    },  # Fromlist: orange
    {
        'red': 1,
        'green': 0.3,
        'blue': 0.3
    },  # Chromium: red
    {
        'red': 0.8,
        'green': 0.8,
        'blue': 0.8
    }  # Other: gray
]


def NOW():
    """Return current time"""
    return int(time.time())


def get_consolidated_topic_name(topic_name, tlist):
    """Return consolidated topic name"""

    for [consolidated_name, topic_names] in tlist:
        for elem in topic_names:
            if topic_name == elem:
                return consolidated_name
    return topic_name


def get_consolidated_topic(c, tlist, topic_name):
    """Return consolidated topic"""

    for (_, topic_names) in tlist:
        for elem in topic_names:
            if topic_name == elem:
                c.execute("select topic from topics where name is '%s'" %
                          topic_names[0])
                topic = c.fetchone()
                if topic:
                    return topic[0]
    c.execute("select topic from topics where name is '%s'" % topic_name)
    topic = c.fetchone()
    if topic:
        return topic[0]
    # oops
    print('No topic found for %s' % topic_name)
    return 0


def get_consolidated_topics(c, tlist):
    """Return dict of consolidated topics"""

    topics = {}
    other_topic_id = None

    c.execute('SELECT topic, name FROM topics ORDER BY name')
    for topic, name in c.fetchall():
        if name:
            consolidated_name = get_consolidated_topic_name(name, tlist)
            consolidated_topic = get_consolidated_topic(c, tlist, name)
            topics[topic] = consolidated_name
            if consolidated_name == 'other':
                other_topic_id = consolidated_topic

    if not other_topic_id:
        topics[genlib.get_other_topic_id(c)] = 'other'

    return topics


def get_tags(cu=None):
    """Get dictionary with list of tags.

    Index is tag, content is tag timestamp
    """

    uconn = None
    if not cu:
        uconn = sqlite3.connect(upstreamdb)
        cu = uconn.cursor()

    tag_list = {}
    largest_ts = 0

    cu.execute('SELECT tag, timestamp FROM tags ORDER BY timestamp')
    for (tag, timestamp) in cu.fetchall():
        tag_list[tag] = timestamp
        if timestamp > largest_ts:
            largest_ts = timestamp

    tag_list[u'ToT'] = largest_ts + 1

    if uconn:
        uconn.close()

    return tag_list


def do_topic_stats_count(topic_stats, tags, topic, committed_ts, integrated_ts):
    """Count commit in topic stats if appropriate"""

    for tag in tags:
        tag_ts = tags[tag]
        if committed_ts < tag_ts < integrated_ts:
            topic_stats[topic][tag] += 1


def get_topic_stats(c):
    """Return dict with commit statistics"""

    uconn = sqlite3.connect(upstreamdb)
    cu = uconn.cursor()

    tags = get_tags(cu)
    topics = get_consolidated_topics(c, topiclist_consolidated)

    topic_stats = {}
    for topic in list(set(topics.values())):
        topic_stats[topic] = {}
        for tag in tags:
            topic_stats[topic][tag] = 0

    c.execute(
        'SELECT usha, dsha, committed, topic, disposition, reason from commits')
    for (
            usha,
            dsha,
            committed,
            topic,
            disposition,
            reason,
    ) in c.fetchall():
        # Skip entries with topic 0 immediately.
        if topic == 0:
            continue
        topic_name = topics.get(topic, 'other')
        if disposition != 'drop':
            do_topic_stats_count(topic_stats, tags, topic_name, committed,
                                 NOW())
            continue
        # disposition is drop.
        if reason == 'fixup/reverted':
            # This patch is a fixup of a reverted and dropped patch, identified
            # by dsha. Count from its commit time up to the revert time.
            # First find the companion (dsha)
            c.execute("SELECT dsha from commits where sha is '%s'" % dsha)
            reverted_dsha, = c.fetchone()
            # Now get the revert time, and count for time in between
            c.execute("SELECT committed from commits where sha is '%s'" %
                      reverted_dsha)
            revert_committed, = c.fetchone()
            do_topic_stats_count(topic_stats, tags, topic_name, committed,
                                 revert_committed)
            continue
        if reason == 'reverted' and dsha:
            # This patch reverts dsha, or it was reverted by dsha.
            # Count only if it was committed after its companion to ensure that
            # it is counted only once.
            c.execute("SELECT committed from commits where sha is '%s'" % dsha)
            revert_committed, = c.fetchone()
            if revert_committed > committed:
                do_topic_stats_count(topic_stats, tags, topic_name, committed,
                                     revert_committed)
            continue
        # This is not a revert, or the revert companion is unknown (which can
        # happen if we reverted an upstream patch). Check if we have a matching
        # upstream or replacement SHA. If so, count accordingly. Don't count
        # if we don't have a matching upstream/replacement SHA.
        if not usha:
            usha = dsha
        if usha:
            cu.execute("SELECT integrated from commits where sha is '%s'" %
                       usha)
            integrated = cu.fetchone()
            if integrated:
                integrated = integrated[0] if integrated[0] else None
            if integrated and integrated in tags:
                do_topic_stats_count(topic_stats, tags, topic_name, committed,
                                     tags[integrated])
            elif not integrated:
                # Not yet integrated.
                # We know that disposition is 'drop', suggesting that the patch was accepted
                # upstream after the most recent tag. Therefore, count against ToT.
                do_topic_stats_count(topic_stats, tags, topic_name, committed,
                                     tags['ToT'])
            else:
                print('sha %s: integrated tag %s not in database' %
                      (usha, integrated))

    uconn.close()

    return topic_stats


def add_topics_summary_row(requests, conn, nconn, sheetId, rowindex, topic, name):
    """Add topics summary row"""

    c = conn.cursor()
    c2 = conn.cursor()
    cn = nconn.cursor()

    age = 0
    now = NOW()
    if topic:
        search = ('select topic, patchid, usha, authored, subject, disposition '
                  'from commits where topic=%d') % topic
    else:
        search = ('select topic, patchid, usha, authored, subject, disposition '
                  'from commits where topic != 0')
    c.execute(search)
    rows = 0
    effrows = 0
    queued = 0
    upstream = 0
    fromlist = 0
    fromgit = 0
    chromium = 0
    backport = 0
    other = 0
    for (t, patchid, usha, a, subject, d) in c.fetchall(): # pylint: disable=too-many-nested-blocks
        if topic == 0:
            # We are interested if the topic name is 'other',
            # or if the topic is not in the named topic list.
            c2.execute('select name from topics where topic is %d' % t)
            topics = c2.fetchone()
            if topics and topics[0] != 'other':
                continue

        rows += 1
        if d == 'pick':
            effrows += 1
            age += (now - a)
            # Search for the patch ID in the next database.
            # If it is found there, count it as "Queued".
            cmd = 'SELECT sha FROM commits WHERE patchid IS "%s"' % patchid
            if usha:
                cmd += ' OR sha IS "%s"' % usha
            cn.execute(cmd)
            if cn.fetchone():
                queued += 1
            else:
                m = rp.search(subject)
                if m:
                    what = m.group(1).replace(' ', '')
                    if what == 'BACKPORT:':
                        m = rp.search(m.group(2))
                        if m:
                            what = m.group(1).replace(' ', '')
                    if what in ('CHROMIUM:', 'CHROMEOS:'):
                        chromium += 1
                    elif what == 'UPSTREAM:':
                        upstream += 1
                    elif what == 'FROMLIST:':
                        fromlist += 1
                    elif what == 'FROMGIT:':
                        fromgit += 1
                    elif what == 'BACKPORT:':
                        backport += 1
                    else:
                        other += 1
                else:
                    other += 1

    # Only add summary entry if there are active commits associated with this topic.
    # Since the summary entry is used to generate statistics, do not add rows
    # where all commits have been pushed upstream or have been reverted.
    if effrows:
        age /= effrows
        age /= (3600 * 24)  # Display age in days
        requests.append({
            'pasteData': {
                'data':
                    '%s;%d;%d;%d;%d;%d;%d;%d;%d;%d;%d' %
                    (name, queued, upstream, backport, fromgit, fromlist,
                     chromium, other, effrows, rows, age),
                'type':
                    'PASTE_NORMAL',
                'delimiter':
                    ';',
                'coordinate': {
                    'sheetId': sheetId,
                    'rowIndex': rowindex
                }
            }
        })
    return effrows


def add_topics_summary(requests, sheetId):
    """Add topics summary"""

    conn = sqlite3.connect(rebasedb)
    nconn = sqlite3.connect(nextdb)
    c = conn.cursor()

    # Handle 'chromeos' first and separately so we can exclude it from the
    # backlog chart later.
    c.execute("select topic from topics where name is 'chromeos'")
    topic = c.fetchone()
    if topic:
        add_topics_summary_row(requests, conn, nconn, sheetId, 1, topic[0], 'chromeos')

    c.execute('select topic, name from topics order by name')
    rowindex = 2
    for (topic, name) in c.fetchall():
        if name not in ('chromeos', 'other'):
            added = add_topics_summary_row(requests, conn, nconn, sheetId, rowindex,
                                           topic, name)
            if added:
                rowindex += 1

    # Finally, do the same for 'other' topics, identified as topic==0.
    added = add_topics_summary_row(requests, conn, nconn, sheetId, rowindex, 0, 'other')

    conn.close()

    return rowindex


def create_summary(sheet, title, sheetId=None):
    """Create summary"""

    requests = []

    if sheetId is None:
        requests.append({
            'addSheet': {
                'properties': {
                    'title': title,
                },
            }
        })
        response = genlib.doit(sheet, requests)
        reply = response.get('replies')
        sheetId = reply[0]['addSheet']['properties']['sheetId']
        requests = []
    else:
        requests.append({
            'updateSheetProperties': {
                'properties': {
                    'sheetId': sheetId,
                    'title': title,
                },
                'fields': 'title'
            }
        })

    header = 'Topic, Queued, Upstream, Backport, Fromgit, Fromlist, \
              Chromium, Untagged/Other, Net, Total, Average Age (days)'

    genlib.add_sheet_header(requests, sheetId, header)

    # Now add all topics
    rows = add_topics_summary(requests, sheetId)

    # As final step, resize it
    genlib.resize_sheet(requests, sheetId, 0, 11)

    # sort by CHROMIUM column, descending
    genlib.sort_sheet(requests, sheetId, 6, 'DESCENDING', rows + 1, 11)

    # and execute
    genlib.doit(sheet, requests)

    return sheetId, rows


def update_one_cell(request, sheetId, row, column, data):
    """Update data in a a single cell"""

    print('update_one_cell(id=%d row=%d column=%d data=%s type=%s' %
          (sheetId, row, column, data, type(data)))

    if isinstance(data, int):
        fieldtype = 'numberValue'
    else:
        fieldtype = 'stringValue'

    request.append({
        'updateCells': {
            'rows': {
                'values': [{
                    'userEnteredValue': {
                        fieldtype: '%s' % data
                    }
                }]
            },
            'fields': 'userEnteredValue(stringValue)',
            'range': {
                'sheetId': sheetId,
                'startRowIndex': row,
                'startColumnIndex': column
                # 'endRowIndex': 1
                # 'endColumnIndexIndex': column + 1
            },
        }
    })


def add_topic_stats_column(request, sheetId, column, tag, data):
    """Add one column of topic statistics to request"""

    row = 0
    update_one_cell(request, sheetId, row, column, tag)

    data.pop(0)  # First entry is topic 0, skip
    for f in data:
        row += 1
        update_one_cell(request, sheetId, row, column, f)


def create_topic_stats(sheet):
    """Create tab with topic statistics.

    We'll use it later to create a chart.
    """

    conn = sqlite3.connect(rebasedb)
    c = conn.cursor()

    topic_stats = get_topic_stats(c)
    tags = get_tags()
    sorted_tags = sorted(tags, key=tags.get)
    topics = get_consolidated_topics(c, topiclist_consolidated)
    topic_list = list(set(topics.values()))

    request = []

    request.append({
        'addSheet': {
            'properties': {
                # 'sheetId': 1,
                'title': 'Topic Statistics Data',
            },
        }
    })

    response = genlib.doit(sheet, request)
    reply = response.get('replies')
    sheetId = reply[0]['addSheet']['properties']['sheetId']

    request = []

    # One column per topic
    header = ''
    columns = 1
    for topic in topic_list:
        header += ', %s' % topic
        columns += 1

    genlib.add_sheet_header(request, sheetId, header)

    rowindex = 1
    for tag in sorted_tags:
        # topic = topics[topic_num]
        # rowdata = topic
        rowdata = tag
        for topic in topic_list:
            rowdata += ';%d' % topic_stats[topic][tag]
        request.append({
            'pasteData': {
                'data': rowdata,
                'type': 'PASTE_NORMAL',
                'delimiter': ';',
                'coordinate': {
                    'sheetId': sheetId,
                    'rowIndex': rowindex
                }
            }
        })
        rowindex = rowindex + 1

    # As final step, resize sheet
    # [not really necessary; drop if confusing]
    genlib.resize_sheet(request, sheetId, 0, columns)

    # and execute
    genlib.doit(sheet, request)

    conn.close()

    return sheetId, rowindex, columns


def colored_scope(name, sheetId, rows, column):
    """Add colored scope"""

    return {
        name: genlib.source_range(sheetId, rows, column),
        'targetAxis': 'LEFT_AXIS',
        'color': stats_colors[column - 1]
    }


def colored_sscope(name, sheetId, rows, start, end):
    """Add colored sscope"""

    s = [colored_scope(name, sheetId, rows, start)]
    while start < end:
        start += 1
        s += [colored_scope(name, sheetId, rows, start)]
    return s


def add_backlog_chart(sheet, dataSheetId, rows):
    """Add backlog chart"""

    request = []

    # chart start with summary row 2. Row 1 is assumed to be 'chromeos'
    # which is not counted as backlog.
    request.append({
        'addChart': {
            'chart': {
                'spec': {
                    'title':
                        'Upstream Backlog (updated %s)' %
                        datetime.datetime.now().strftime('%x'),
                    'basicChart': {
                        'chartType': 'COLUMN',
                        'stackedType': 'STACKED',
                        'headerCount': 1,
                        # "legendPosition": "BOTTOM_LEGEND",
                        'axis': [{
                            'position': 'BOTTOM_AXIS',
                            'title': 'Topic'
                        }, {
                            'position': 'LEFT_AXIS',
                            'title': 'Backlog'
                        }],
                        'domains': [genlib.scope('domain', dataSheetId, rows + 1, 0)],
                        'series': colored_sscope('series', dataSheetId, rows + 1, 1, 7),
                    }
                },
                'position': {
                    'newSheet': True,
                }
            }
        }
    })

    response = genlib.doit(sheet, request)

    # Extract sheet Id from response
    reply = response.get('replies')
    sheetId = reply[0]['addChart']['chart']['position']['sheetId']

    request = []
    request.append({
        'updateSheetProperties': {
            'properties': {
                'sheetId': sheetId,
                'title': 'Backlog Count',
            },
            'fields': 'title',
        }
    })
    genlib.doit(sheet, request)


def add_age_chart(sheet, dataSheetId, rows):
    """Add age chart"""

    request = []

    request.append({
        'addChart': {
            'chart': {
                'spec': {
                    'title':
                        'Upstream Backlog Age (updated %s)' %
                        datetime.datetime.now().strftime('%x'),
                    'basicChart': {
                        'chartType': 'COLUMN',
                        'headerCount': 1,
                        # "legendPosition": "BOTTOM_LEGEND",
                        'axis': [{
                            'position': 'BOTTOM_AXIS',
                            'title': 'Topic'
                        }, {
                            'position': 'LEFT_AXIS',
                            'title': 'Average Age (days)'
                        }],
                        'domains': [genlib.scope('domain', dataSheetId, rows + 1, 0)],
                        'series': [genlib.scope('series', dataSheetId, rows + 1, 10)]
                    }
                },
                'position': {
                    'newSheet': True,
                }
            }
        }
    })

    response = genlib.doit(sheet, request)

    # Extract sheet Id from response
    reply = response.get('replies')
    sheetId = reply[0]['addChart']['chart']['position']['sheetId']

    request = []
    request.append({
        'updateSheetProperties': {
            'properties': {
                'sheetId': sheetId,
                'title': 'Backlog Age',
            },
            'fields': 'title',
        }
    })
    genlib.doit(sheet, request)


def add_stats_chart(sheet, dataSheetId, rows, columns):
    """Add statistics chart"""

    request = []

    if columns > 25:
        print('########### Limiting number of columns to 25 from %d' % columns)
        columns = 25

    request.append({
        'addChart': {
            'chart': {
                'spec': {
                    'title':
                        'Topic Statistics (updated %s)' %
                        datetime.datetime.now().strftime('%x'),
                    'basicChart': {
                        'chartType':
                            'AREA',
                        'stackedType':
                            'STACKED',
                        'headerCount':
                            1,
                        # "legendPosition": "BOTTOM_LEGEND",
                        'axis': [{
                            'position': 'BOTTOM_AXIS',
                            'title': 'Upstream Release Tag'
                        }, {
                            'position': 'LEFT_AXIS',
                            'title': 'Patches'
                        }],
                        'domains': [genlib.scope('domain', dataSheetId, rows, 0)],
                        'series':
                            genlib.sscope('series', dataSheetId, rows, 1, columns),
                    }
                },
                'position': {
                    'newSheet': True,
                }
            }
        }
    })

    response = genlib.doit(sheet, request)

    # Extract sheet Id from response
    reply = response.get('replies')
    sheetId = reply[0]['addChart']['chart']['position']['sheetId']

    request = []
    request.append({
        'updateSheetProperties': {
            'properties': {
                'sheetId': sheetId,
                'title': 'Topic Statistics',
            },
            'fields': 'title',
        }
    })
    genlib.doit(sheet, request)


def main():
    """Main function"""

    sheet = genlib.init_spreadsheet(
        stats_filename,
        'Backlog Status for chromeos-%s' % rebase_baseline().strip('v'))

    summary_sheet, summary_rows = create_summary(sheet, 'Backlog Data', 0)
    topic_stats_sheet, topic_stats_rows, topic_stats_columns = create_topic_stats(
        sheet)

    add_backlog_chart(sheet, summary_sheet, summary_rows)
    add_age_chart(sheet, summary_sheet, summary_rows)
    add_stats_chart(sheet, topic_stats_sheet, topic_stats_rows,
                    topic_stats_columns)

    # Move data sheets to the very end
    genlib.move_sheet(sheet, summary_sheet, 5)
    genlib.move_sheet(sheet, topic_stats_sheet, 5)

    # and hide them
    genlib.hide_sheet(sheet, summary_sheet, True)
    genlib.hide_sheet(sheet, topic_stats_sheet, True)


if __name__ == '__main__':
    main()
