#!/usr/bin/env python3
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module contains shared helper functions for gfx scripts"""

from __future__ import print_function

import json
import os
import sys
import subprocess
import traceback


def panic(msg: str, exit_code: int = 1):
  """Exits the process with message and error code

  Dumps error message along with callstack and exits the application with
  specified exit code
  """
  print('-' * 60, file=sys.stderr)
  print('ERROR: %s' % msg, file=sys.stderr)
  print('-' * 60, file=sys.stderr)
  traceback.print_exc(file=sys.stderr)
  print('-' * 60, file=sys.stderr)
  sys.exit(exit_code)


def parse_json_file(file_name):
  """Parses the given JSON file and returns the result as a dictionary object"""
  try:
    with open(file_name) as json_file:
      return json.loads(json_file)
  except Exception as e:
    print('ERROR: ' + str(e))
    return None


def parse_cmd_stdout_json(cmd):
  """Parses command's standard output JSON and returns the result as a dictionary object"""
  try:
    result = subprocess.run(
        cmd,
        check=True,
        encoding='utf-8',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)
    return json.loads(result.stdout)
  except Exception as e:
    print('ERROR: ' + str(e))
    return None


def parse_script_stdout_json(script, args):
  """Parses script's standard output JSON and returns the result as a dictionary object"""
  cmd = [os.path.join(os.path.dirname(os.path.realpath(__file__)), script)
        ] + args
  return parse_cmd_stdout_json(cmd)
