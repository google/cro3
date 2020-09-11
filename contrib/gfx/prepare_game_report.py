#!/usr/bin/env python3
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This script prepares an archive which includes all the necessary information for a game report along with its trace file."""

from __future__ import print_function

import apt
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import utils

GAME_REPORT_VERSION = '2'
TRACE_STORAGE_REPORT_VERSION = '3'
TMP_DIR = '/tmp'
DEFAULT_TRACE_FNAME = 'game.trace'
TRACE_INFO_FNAME = 'trace_info.json'
GAME_INFO_FNAME = 'game_info.json'
SYSTEM_INFO_FNAME = 'system_info.json'
REQUIRED_PACKAGES = ['apitrace', 'tar', 'zstd']


def yes_or_no(question):
  """Prints the 'question', waits for 'yes' or 'no' input and then returns the result as Boolean"""
  while 'the answer is invalid':
    reply = input(question + ' (y/n): ').lower().strip()
    if reply[:1] == 'y':
      return True
    if reply[:1] == 'n':
      return False


def get_file_checksum(file_name, file_hash):
  """Returns 'file_hash' based checksum of the specified file"""
  with open(file_name, 'rb') as f:
    while True:
      chunk = f.read(1024 * 1024)
      if not chunk:
        break
      file_hash.update(chunk)
  return file_hash.hexdigest()


def get_file_sha256(file_name):
  """Returns SHA256 checksum of the specified file"""
  return get_file_checksum(file_name, hashlib.sha256())


def get_file_md5(file_name):
  """Returns MD5 checksum of the specified file"""
  return get_file_checksum(file_name, hashlib.md5())


def save_json(data, file_name):
  """Writes given 'data' into file_name in JSON format"""
  with open(file_name, 'w') as f:
    f.write(json.dumps(data, indent=2))


def parse_json_file(file_name):
  """Parses the given JSON file and returns the result as a dictionary object"""
  try:
    with open(file_name) as json_file:
      return json.loads(json_file)
  except Exception as e:
    return None


def parse_script_stdout_json(script, args):
  """Parses script's standart output JSON and returns the result as a dictionary object"""
  try:
    cmd = [os.path.join(os.path.dirname(os.path.realpath(__file__)), script)
          ] + args
    result = subprocess.run(
        cmd, check=True, encoding='utf-8', capture_output=True)
    return json.loads(result.stdout)
  except Exception as e:
    return None


def main(args):
  defaultTraceFileName = os.path.join(TMP_DIR, DEFAULT_TRACE_FNAME)
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('gameid', help='steam game id')
  parser.add_argument(
      '--temp-dir',
      default=TMP_DIR,
      dest='temp_dir',
      help=f'working directory for temp files (default: {TMP_DIR})')
  parser.add_argument(
      '--sysinfo-file',
      dest='sysinfo_file',
      help='override the system info with the given json file')
  parser.add_argument(
      '--output-dir',
      default=TMP_DIR,
      dest='output_dir',
      help=f'the output directory for the result file (default: {TMP_DIR})'
  )
  parser.add_argument(
      '--trace-file',
      default=defaultTraceFileName,
      dest='trace_file',
      help=f'game trace file name (default: {defaultTraceFileName})')
  opts = parser.parse_args(args)

  if opts.sysinfo_file and not os.path.exists(opts.sysinfo_file):
    utils.panic(
        f'Unable to open system info file {opts.sysinfo_file}. File not found.')

  if opts.trace_file != defaultTraceFileName and not os.path.exists(
      opts.trace_file):
    utils.panic(f'Unable to open trace file {opts.trace_file}. File not found.')

  # Check for missing packages
  cache = apt.Cache()
  for p in REQUIRED_PACKAGES:
    if not p in cache or not cache[p].is_installed:
      utils.panic(f'The required package "{p}" isn\'t installed.')

  try:
    cur_time = datetime.datetime.now(
        datetime.timezone.utc).astimezone().replace(microsecond=0)
    items_in_archive = [GAME_INFO_FNAME, SYSTEM_INFO_FNAME]

    # Retrieving the game information from Steam.
    print('Retrieving the game information from Steam...')
    game_info = parse_script_stdout_json('steam_game_info.py', [opts.gameid])
    if not game_info:
      utils.panic(
          f'Unable to retrieve information for the game with steamid {opts.gameid}'
      )
    print(f'Steam game id: {game_info["gameid"]}')
    print(f'Game name: {game_info["game_name"]}')
    if not yes_or_no('Is it correct?'):
      sys.exit(0)

    # Format the output file name
    game_name_safe = re.sub('[^a-z0-9]', '_', game_info['game_name'].lower())
    result_name = 'steam_%s-%s-%s' % (opts.gameid, game_name_safe,
                                      cur_time.strftime('%Y%m%d_%H%M%S'))
    result_file_name = f'{result_name}.tar'
    result_full_name = os.path.join(opts.output_dir, result_file_name)

    # Sanity check file/directory paths for collisions.
    if os.path.exists(result_full_name):
      if yes_or_no(
          f'The file {result_full_name} already exists. Do you want to delete it?'
      ):
        os.remove(result_full_name)
      else:
        sys.exit(0)

    # Collect the game info report.
    game_info.update({
        'report_version': GAME_REPORT_VERSION,
        'report_date': cur_time.isoformat(),
        'game_version': input('Game version (if available): '),
        'can_start': yes_or_no('Does the game start?'),
        'bug_id': input('Issue id in buganizer: '),
    })
    if game_info['can_start']:
      game_info.update({
          'load_time': input('Game load time to main menu in seconds: '),
          'fps_main_menu': input('Main menu fps: '),
          'start_time': input('Game start time from main menu in seconds: '),
          'playable': yes_or_no('Is game playable?'),
          'stutters': yes_or_no('Does game stutter?'),
          'average_fps': input('Average game fps: '),
          'full_screen': yes_or_no('Is game fullscreen?'),
      })
    else:
      game_info['can_install'] = yes_or_no('Does the game install?')
      if not game_info['can_install']:
        game_info['not_enough_space'] = yes_or_no(
            'Is the installation error caused by insufficient disk space?')
    save_json(game_info, os.path.join(opts.temp_dir, GAME_INFO_FNAME))

    # Collect system/machine info report.
    if opts.sysinfo_file:
      print(f'Using system information from {opts.sysinfo_file}')
      shutil.copyfile(opts.sysinfo_file,
                      os.path.join(opts.temp_dir, SYSTEM_INFO_FNAME))
    else:
      system_info = {}
      system_info['host'] = {
          'chrome':
              input('Paste "Google Chrome" string from chrome://version: '),
          'platform':
              input('Paste "Platform" string from chrome://version: ')
      }
      print('Collecting cros container system information...')
      system_info['guest'] = parse_script_stdout_json('cros_container_info.py',
                                                      [])
      save_json(system_info, os.path.join(opts.temp_dir, SYSTEM_INFO_FNAME))

    if (game_info['can_start'] and
        yes_or_no('Did you manage to create the trace file?')):
      print(f'Preparing the trace file information for {opts.trace_file}...')
      trace_info = parse_script_stdout_json('trace_file_info.py',
                                            [opts.trace_file])
      if trace_info == None:
        utils.panic('Unable to retrieve the game trace information')
      file_time = datetime.datetime.fromtimestamp(
          os.path.getmtime(opts.trace_file)).astimezone().replace(microsecond=0)
      trace_info.update({
          'trace_file_name':
              DEFAULT_TRACE_FNAME,
          'trace_file_size':
              os.path.getsize(opts.trace_file),
          'trace_file_time':
              file_time.isoformat(),
          'trace_file_md5':
              get_file_md5(opts.trace_file),
          'trace_can_replay':
              yes_or_no('Does the trace file can be replayed without crashes?'),
      })
      if trace_info['trace_can_replay']:
        trace_info['trace_replay_artifacts'] = yes_or_no(
            'Is there any visual differences in trace replay compared to the game?'
        )
        trace_info['trace_replay_fps'] = input('Trace replay fps: ')
      print('Compressing the trace file...')
      trace_storage_file_name = DEFAULT_TRACE_FNAME + '.zst'
      trace_storage_full_name = os.path.join(opts.temp_dir,
                                             trace_storage_file_name)
      zstd_cmd = [
          'zstd', '-T0', '-f', opts.trace_file, '-o', trace_storage_full_name
      ]
      subprocess.run(zstd_cmd, check=True)
      trace_info.update({
          'report_version': TRACE_STORAGE_REPORT_VERSION,
          'storage_file_name': trace_storage_file_name,
          'storage_file_size': os.path.getsize(trace_storage_full_name),
          'storage_file_sha256': get_file_sha256(trace_storage_full_name),
          'storage_file_md5': get_file_md5(trace_storage_full_name),
      })
      save_json(trace_info, os.path.join(opts.temp_dir, TRACE_INFO_FNAME))
      items_in_archive = items_in_archive + [
          TRACE_INFO_FNAME, trace_storage_file_name
      ]

    # Finally put everything in a tarball. The --transform option is used to replace
    # initial ./ prefix with {$result_name}/
    print(f'Archiving the result to {result_full_name}...')

    tar_cmd = [
        'tar', '-cf', result_full_name, '--transform', f's,^,{result_name}/,'
    ] + items_in_archive
    subprocess.run(tar_cmd, check=True, cwd=opts.temp_dir)
  except Exception as e:
    utils.panic(str(e))

  print('Done')


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
