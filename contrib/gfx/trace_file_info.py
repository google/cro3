#!/usr/bin/env python3
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import print_function
import argparse
from datetime import datetime
import json
import hashlib
from os import path
import subprocess
import sys
from time import mktime

# This script retreives the specified trace file's information and outputs it
# in JSON format

def panic(msg, exit_code):
  print('ERROR: %s' % msg, file=sys.stderr)
  exit(exit_code)

def get_file_md5(file_name):
  file_hash = hashlib.md5()
  with open(file_name, 'rb') as f:
    while True:
      chunk = f.read(1024 * 1024)
      if not chunk:
        break;
      file_hash.update(chunk)
  return file_hash.hexdigest()

if sys.version_info[0] < 3:
  panic("Must run script using python3", -1)

parser = argparse.ArgumentParser(description=
  'Retreives the specified trace file information')
parser.add_argument('trace_file', help='.trace file name')
args = parser.parse_args()

trace_fname = args.trace_file
if path.isfile(trace_fname) != True:
  panic('Unable to open <%s>. File not found.' % trace_fname, -1)

try:
  cmd = 'apitrace info --json %s' % trace_fname
  output = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, encoding='utf-8').stdout
except subprocess.CalledProcessError as err:
  panic('Unable to retreive <%s> information.' % trace_fname, -1)

try:
  res = json.loads(output)
  data_results = {}
  data_results['trace_file_version'] = res['FileVersion']
  data_results['trace_frames_count'] = res['FramesCount']
  data_results['trace_file_name'] = trace_fname
  data_results['trace_file_size'] = path.getsize(trace_fname)
  file_time = datetime.fromtimestamp(
                path.getmtime(trace_fname)).astimezone().replace(microsecond=0)
  data_results['trace_file_time'] = file_time.isoformat()
  data_results['trace_file_md5'] = get_file_md5(trace_fname)
  print(json.dumps(data_results, indent=2, sort_keys=True))
except Exception as err:
  panic('Unable to decode apitrace info output: <%s>' % str(err), -1)
