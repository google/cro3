#!/usr/bin/env python3
# -*- coding: utf-8 -*
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Collects the current list of the Top 'N' Linux games on Steam."""

from __future__ import print_function

import argparse
import datetime
import http
import http.client
import json
import os
import re
import subprocess
import sys
import urllib.request
import utils

REPORT_VERSION = '1'
MAX_CHART_PAGE = 25

# Disable Bad indentation error in repo upload.
# pylint: disable-msg=W0311

# Disable catching too general exception Exception.
# pylint: disable-msg=W0703

def get_games_on_page(page):
  """Returns the list of game  identifiers from the given page of the top steam games chart"""
  data = ''
  try:
    req = urllib.request.Request(
        f'https://steamcharts.com/top/p.{page}',
        headers={'User-Agent': 'Magic Browser'})
    with urllib.request.urlopen(req) as resp:
      if resp.status != http.HTTPStatus.OK:
        raise Exception('Unable to get <%s>. Response is %s' %
                        (resp.reason, resp.status))
      data = resp.read().decode('utf-8')
  except Exception as e:
    utils.panic('Unable to retrieve the steam charts data: %s' % str(e))

  result = []
  try:
    re_res = re.findall(r'<td id="spark_(\d+)"', data, re.MULTILINE)
    result.extend(re_res)
  except Exception:
    utils.panic('Unable to parse steamdb.info response')
  return result

def parse_script_stdout_json(script, args):
  """Parses script's standart output JSON and returns as a dictionary object"""
  try:
    cmd = [os.path.join(os.path.dirname(os.path.realpath(__file__)), script)
          ] + args
    output = subprocess.run(
        cmd, check=True, encoding='utf-8', capture_output=True)
    return json.loads(output.stdout)
  except Exception as e:
    print(f'failed to run {script}: {e}')
    return None


def main(args):
  """main function."""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('games_count', type=int, help='Number of games to print')
  parser.add_argument(
      'out_file', help='Output file name with extension .json or .csv')
  opts = parser.parse_args(args)

  out_file_type = os.path.splitext(opts.out_file)[1]
  if out_file_type not in ('.json', '.csv'):
    parser.error('Output file must have .csv or .json extension')

  try:
    print(f'Preparing the list of the Top {opts.games_count} Linux games...')
    cur_game_pos = 1
    cur_chart_page = 1
    result = {'report_version': REPORT_VERSION}
    cur_time = datetime.datetime.now(
        datetime.timezone.utc).astimezone().replace(microsecond=0)
    result['report_date'] = cur_time.isoformat()
    games = []
    while len(games) < opts.games_count and cur_chart_page <= MAX_CHART_PAGE:
      game_ids = get_games_on_page(cur_chart_page)
      for game_id in game_ids:
        game_info = parse_script_stdout_json('steam_game_info.py', [game_id])
        print('Processing [%s]  ' % game_id, end='')
        if game_info:
          print('%s: ' % game_info['game_name'], end='')
          if 'Linux' in game_info['platforms']:
            game_info['chart_position'] = cur_game_pos
            games.append(game_info)
            print('Added')
          else:
            print('Skipped (no Linux support)')
          cur_game_pos += 1
        else:
          print('Skipped (unable to parse game info output)')
        if len(games) == opts.games_count:
          break
      cur_chart_page += 1

    result['games'] = games

    with open(opts.out_file, 'w', encoding='utf-8') as out_file:
      if out_file_type == '.json':
        out_file.write(json.dumps(result, indent=2))
      elif out_file_type == '.csv':

        def support(platform_list, platform):
          """Return formatted True/False if platform is in platform_list"""
          if platform in platform_list:
            return 'TRUE'
          return 'FALSE'

        out_file.write('gameid,game_name,chart_pos,linux,windows,macos\n')
        for game in games:
          out_file.write(','.join([
              game['gameid'], game['game_name'].replace(',', ' '),
              str(game['chart_position']),
              support(game['platforms'], 'Linux'),
              support(game['platforms'], 'Windows'),
              support(game['platforms'], 'macOS')
          ]) + '\n')

  except Exception as e:
    utils.panic(str(e))


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
