#!/usr/bin/env python3
# Copyright 2019 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
from __future__ import print_function
import subprocess
import argparse
from collections import namedtuple
import json
import os
import re

# This script collects all the necessary system information and outputs it in JSON format

SYSINFO_REPORT_VERSION = '1'

def default_parser(s):
  return s

def package_list_parser(s):
  res = re.findall(r'(.*)\#\#(.*)', s)
  if len(res) == 1:
    return { res[0][0] : res[0][1] }
  return s

cmd_data_sources = {
  'linux_version' : {
    'cmd' :'uname -a'
  },
  'packages' : {
    'cmd' : 'dpkg-query -f \'${binary:Package}##${source:Version}\n\' -W \'*\'',
    'parser' : package_list_parser
  },
  'sources_list' : {
    'cmd' : 'cat /etc/apt/sources.list'
  },
  'sources_list_d' : {
    'cmd' : 'cat /etc/apt/sources.list.d/*'
  },
  'glx_device' : {
    'cmd' : 'glxinfo -B | grep Device: | cut -f2- -d:'
  }
}

def run_app(cmd_line, parser):
  return list(map(parser, subprocess.run(cmd_line, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding='utf-8').stdout.splitlines()))

data_results = {}
data_results['report_version'] = SYSINFO_REPORT_VERSION

for key in cmd_data_sources:
  parser = cmd_data_sources[key].get('parser', default_parser)
  data_results[key] = run_app(cmd_data_sources[key]['cmd'], parser)

print(json.dumps(data_results, indent=2, sort_keys=True))

