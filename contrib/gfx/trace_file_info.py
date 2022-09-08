#!/usr/bin/env python3
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Prints the specified trace file information in JSON format"""

from __future__ import print_function

import argparse
import hashlib
import json
import os
import subprocess
import sys
import utils


def main(args):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('trace_file', help='.trace file name')
  opts = parser.parse_args(args)

  trace_fname = opts.trace_file
  if not os.path.isfile(trace_fname):
    utils.panic('Unable to open <%s>. File not found.' % trace_fname)

  try:
    cmd = ['apitrace', 'info', trace_fname]
    result = subprocess.run(
        cmd,
        check=True,
        encoding='utf-8',
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE)

    res = json.loads(result.stdout)
    data_results = {
        'trace_file_version': res['ContainerVersion'],
        'trace_frames_count': res['FramesCount'],
    }
    print(json.dumps(data_results, indent=2, sort_keys=True))
  except subprocess.CalledProcessError as e:
    utils.panic(f'Unable to retreive {trace_fname} information. {str(e)}')
  except Exception as e:
    utils.panic(f'Unable to decode apitrace info output: <{str(e)}>')


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
