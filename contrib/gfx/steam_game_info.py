#!/usr/bin/env python3
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import print_function
import html
import http.client
import ssl
import re
import argparse
import json
import sys

# This script retreives the specified game information from the Steam DB

parser = argparse.ArgumentParser(description=
  'Retreives the specified game information from the Steam DB.')
parser.add_argument('gameid', help='Steam application/game id')
args = parser.parse_args()
ssl_context = ssl.create_default_context()
conn = http.client.HTTPSConnection('steamdb.info', context=ssl_context)
try:
  headers = {
      'User-Agent':
          'Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) '
          'Chrome/81.0.2228.0 Safari/537.36',
  }
  conn.request('GET', '/app/%s/' % args.gameid, None, headers)
  resp = conn.getresponse()
  if resp.status != 200:
    raise Exception(f'Response status is {resp.status} (expected 200)')
except Exception as err:
  print('Unable to retrieve the data for the game with id %s: %s' % (args.gameid, str(err)),
        file=sys.stderr)
  conn.close()
  exit(-1)

data = resp.read().decode('utf-8')

conn.close()

data_results = {}
data_results['gameid'] = args.gameid
try:
  data_results['game_name'] = html.unescape(re.findall(r'\<h1 itemprop\=\"name\"\>(.*?)\<\/h1\>',
                                                       data, re.MULTILINE)[0])
  data_results['platforms'] = re.findall(r'operatingSystem\" content\="(.*?)\"\>',
                                         data, re.MULTILINE)[0]
except Exception:
  print('Unable to parse steamdb.info response')
  exit(-1)

print(json.dumps(data_results, indent=2, sort_keys=True))
