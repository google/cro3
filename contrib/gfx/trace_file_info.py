#!/usr/bin/env python3
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import print_function
import argparse
import subprocess
import sys
from os import path
import time
import json

# This script retreives the specified trace file's information and outputs it
# in JSON format

TRACEINFO_REPORT_VERSION = '1'

def panic(msg, exit_code):
  print('ERROR: %s' % msg, file=sys.stderr)
  exit(exit_code)

if sys.version_info[0] < 3:
  panic("Must run script using python3", -1)

parser = argparse.ArgumentParser(description=
  'Retreives the specified trace file information')
parser.add_argument('trace_file', help='.trace file name')
args = parser.parse_args()

if path.isfile(args.trace_file) != True:
  panic('Unable to open <%s>. File not found.' % args.trace_file, -1)

try:
  cmd = 'apitrace info --json %s' % args.trace_file
  output = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, encoding='utf-8').stdout
except subprocess.CalledProcessError as err:
  panic('Unable to retreive <%s> information.' % args.trace_file, -1)

try:
  res = json.loads(output)
  data_results = {}
  data_results['report_version'] = TRACEINFO_REPORT_VERSION
  data_results['trace_file_version'] = res['FileVersion']
  data_results['trace_frames_count'] = res['FramesCount']
  data_results['file_size'] = path.getsize(args.trace_file)
  data_results['file_ctime'] = time.ctime(path.getctime(args.trace_file))
  print(json.dumps(data_results, indent=2, sort_keys=True))
except Exception as err:
  panic('Unable to decode apitrace info output: <%s>' % str(err), -1)
