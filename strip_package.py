#!/usr/bin/python

# Copyright (c) 2009-2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script that strips a given package and places the stripped version in
   <sysroot>/stripped-packages."""

import optparse
import sys

import builder


def main():
  parser = optparse.OptionParser(usage='usage: %prog [options] package')
  parser.add_option('--board', type='string', action='store',
                    help=('The board that the package being processed belongs '
                          'to.'))
  parser.add_option('--sysroot', type='string', action='store',
                    help=('Sysroot that the package being processed belongs to.'
                          'This is incompatible with --board.'))
  parser.add_option('--deep', action='store_true', default=False,
                    help=('Also strip dependencies of package.'))

  (options, args) = parser.parse_args()
  if len(args) != 1:
    parser.print_help()
    parser.error('Need exactly one package name')

  if not options.board and not options.sysroot:
    parser.error('Need to specify --board or --sysroot.')

  if options.board and options.sysroot:
    parser.error('--board and --sysroot are mutually exclusive.')

  sysroot = options.sysroot or '/build/%s/' % options.board

  # Check if package was installed.
  if not builder.UpdateGmergeBinhost(sysroot, args[0], options.deep):
    sys.exit(1)


if __name__ == '__main__':
  main()
