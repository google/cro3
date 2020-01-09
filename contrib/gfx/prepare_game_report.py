#!/usr/bin/env python3
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import print_function
import argparse
import sys
import subprocess
import json
from os import path
from datetime import date

# This script prepares an archive which includes all the necessary information
# for a game report along with its trace file.

python_bin = 'python3'
tmp_dir = '/tmp'
game_trace_fname = 'game.trace'
trace_info_fname = 'trace_info.json'
game_info_fname = 'game_info.json'
system_info_fname = 'system_info.json'
files_in_archive = [game_info_fname, system_info_fname]

def yes_or_no(question):
  while "the answer is invalid":
    reply = str(input(question+' (y/n): ')).lower().strip()
    if reply[:1] == 'y':
      return True
    if reply[:1] == 'n':
      return False

def panic(msg, exit_code):
  print('ERROR: %s' % msg, file=sys.stderr)
  exit(exit_code)

def save_json(data, file_name):
  with open(file_name, 'w') as f:
    f.write(json.dumps(data, indent=2))

# Parses script's standart output JSON and returns as a dictionary object.
def parse_script_stdout_json(script, args):
  cmd = [python_bin, path.join(path.dirname(path.realpath(__file__)), script)] + args
  output = subprocess.run(' '.join(cmd), shell=True, check=True, encoding='utf-8',
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
  return json.loads(output.stdout)

if sys.version_info[0] < 3:
  panic("Must run script using python3", -1)

parser = argparse.ArgumentParser()
parser.add_argument('gameid')
args = parser.parse_args()

try:
  # Collect the game info report.
  print('Retreiving the game information...')
  game_info = parse_script_stdout_json('steam_game_info.py', [args.gameid])
  print('Steam game id: %s' % game_info['gameid'])
  print('Game name: %s' % game_info['game_name'])
  if yes_or_no('Is it correct?') != True:
    exit(0)
  game_info['report_date'] = date.today().strftime("%m/%d/%Y")
  game_info['version'] = input("Game version (if available): ")
  game_info['can_start'] = yes_or_no('Does the game start?')
  game_info['bug_id'] = input('Issue id in buganizer (if available): ')
  if game_info['can_start'] == True:
    game_info['load_time'] = input('Game load time to main menu in seconds: ')
    game_info['fps_main_menu'] = input('Main menu fps: ')
    game_info['start_time'] = input('Game start time from main menu in seconds: ')
    game_info['playable'] = yes_or_no('Is game playable?')
    game_info['average_fps'] = input('Average game fps: ')
  save_json(game_info, path.join(tmp_dir, game_info_fname))

  # Collect system/machine info report.
  system_info = {}
  system_info['host'] = {
    'chrome' : input('Paste \'Google Chrome\' string from chrome://version: '),
    'platform' : input('Paste \'Platform\' string from chrome://version: ')
  }
  print('Collecting cros container system information...')
  system_info['guest'] = parse_script_stdout_json('cros_container_info.py', [])
  save_json(system_info, path.join(tmp_dir, system_info_fname))

  if (
      game_info['can_start']
      and yes_or_no('Did you manage to create the trace file?') == True
  ):
    print('Preparing the trace file information for %s...' % game_trace_fname)
    trace_info = parse_script_stdout_json('trace_file_info.py',
                   [path.join(tmp_dir, game_trace_fname)])
    save_json(trace_info, path.join(tmp_dir, trace_info_fname))
    files_in_archive = files_in_archive + [game_trace_fname, trace_info_fname]

  # Finally compress everything.
  result_fname = '%s_game_report.tar.bz2' % (args.gameid)
  print('Archiving the result to %s ...' % result_fname)
  compress_cmd = 'tar -caf %s %s' % (result_fname, ' '.join(files_in_archive))
  subprocess.run(compress_cmd, shell=True, check=True, cwd=tmp_dir)

except Exception as e:
  panic(str(e), -1)

print('Done')
