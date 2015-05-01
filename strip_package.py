#!/usr/bin/python2
# Copyright (c) 2009-2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Strip package and place it in <sysroot>/stripped-packages."""

from __future__ import print_function

import argparse
import sys

import builder


def main():
  parser = argparse.ArgumentParser()
  target = parser.add_mutually_exclusive_group(required=True)
  target.add_argument('--board',
                      help=('The board that the package being processed '
                            'belongs to'))
  target.add_argument('--sysroot',
                      help=('Sysroot that the package being processed belongs '
                            'to. This is incompatible with --board.'))
  parser.add_argument('--deep', action='store_true',
                      help='Also strip dependencies of package.')
  parser.add_argument('package', help='Package to strip.')

  options = parser.parse_args()
  sysroot = options.sysroot or '/build/%s' % options.board

  # Check if package was installed.
  if not builder.UpdateGmergeBinhost(sysroot, options.package, options.deep):
    sys.exit(1)


if __name__ == '__main__':
  main()
