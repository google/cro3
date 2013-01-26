#!/usr/bin/python
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Command-line tool for checking and applying Chrome OS update payloads."""

import optparse
import os
import sys

# pylint: disable=F0401
lib_dir = os.path.join(os.path.dirname(__file__), 'lib')
if os.path.exists(lib_dir) and os.path.isdir(lib_dir):
  sys.path.insert(1, lib_dir)
import update_payload


_TYPE_FULL = 'full'
_TYPE_DELTA = 'delta'


def ParseArguments(parser, argv):
  """Parse and validate command-line arguments.

  Args:
    parser: the command-line parser
  Returns:
    A tuple (options, payload, extra_args), where `options' are the options
    returned by the parser, `payload' is the name of the payload file
    (mandatory argument) and `extra_args' are any additional command-line
    arguments.

  """
  options, args = parser.parse_args(argv)

  # Validate a value given to --type, if any.
  if options.assert_type not in (None, _TYPE_FULL, _TYPE_DELTA):
    parser.error('invalid argument to --type: %s' % options.assert_type)

  # There are several options that imply --check.
  options.check = (options.check or options.report or options.assert_type or
                   options.block_size or options.allow_unhashed or
                   options.key or options.meta_sig)

  # Check number of arguments, enforce payload type accordingly.
  if len(args) == 3:
    if options.assert_type == _TYPE_DELTA:
      parser.error('%s payload requires source partition arguments' %
                   _TYPE_DELTA)
    options.assert_type = _TYPE_FULL
  elif len(args) == 5:
    if options.assert_type == _TYPE_FULL:
      parser.error('%s payload does not accept source partition arguments' %
                   _TYPE_FULL)
    options.assert_type = _TYPE_DELTA
  elif len(args) != 1:
    parser.error('unexpected number of arguments')

  return options, args[0], args[1:]


def main(argv):
  parser = optparse.OptionParser(
      usage='Usage: %prog [OPTION...] PAYLOAD [DST_KERN DST_ROOT '
            '[SRC_KERN SRC_ROOT]]',
      description='Applies a Chrome OS update PAYLOAD to SRC_KERN and '
                  'SRC_ROOT emitting DST_KERN and DST_ROOT, respectively. '
                  'SRC_KERN and SRC_ROOT need only be provided for delta '
                  'payloads. If no partitions are provided, only verifies '
                  'payload integrity.')

  check_opts = optparse.OptionGroup(parser, 'Payload checking')
  check_opts.add_option('-c', '--check', action='store_true', default=False,
                        help='check payload integrity')
  check_opts.add_option('-r', '--report', metavar='FILE',
                        help="dump payload report (`-' for stdout)")
  check_opts.add_option('-t', '--type', metavar='TYPE', dest='assert_type',
                        help="assert that payload is either `%s' or `%s'" %
                             (_TYPE_FULL, _TYPE_DELTA))
  check_opts.add_option('-z', '--block-size', metavar='NUM', default=0,
                        type='int',
                        help='assert a non-default (4096) payload block size')
  check_opts.add_option('-u', '--allow-unhashed', action='store_true',
                        default=False, help='allow unhashed operations')
  check_opts.add_option('-k', '--key', metavar='FILE',
                        help='public key to be used for signature verification')
  check_opts.add_option('-m', '--meta-sig', metavar='FILE',
                        help='verify metadata against its signature')
  parser.add_option_group(check_opts)

  trace_opts = optparse.OptionGroup(parser, 'Block tracing')
  trace_opts.add_option('-b', '--root-block', metavar='BLOCK', type='int',
                        help='trace the origin for a rootfs block')
  trace_opts.add_option('-B', '--kern-block', metavar='BLOCK', type='int',
                        help='trace the origin for a kernel block')
  trace_opts.add_option('-s', '--skip', metavar='NUM', default='0', type='int',
                        help='skip first NUM occurrences of traced block')
  parser.add_option_group(trace_opts)

  # Parse and validate arguments.
  options, payload_file_name, extra_args = ParseArguments(parser, argv[1:])

  with open(payload_file_name) as payload_file:
    payload = update_payload.Payload(payload_file)
    try:
      # Initialize payload.
      payload.Init()

      # Perform payload integrity checks.
      if options.check:
        report_file = None
        do_close_report_file = False
        try:
          if options.report:
            if options.report == '-':
              report_file = sys.stdout
            else:
              report_file = open(options.report, 'w')
              do_close_report_file = True

          payload.Check(
              pubkey_file_name=options.key,
              metadata_sig_file=open(options.meta_sig)
              if options.meta_sig else None,
              report_out_file=report_file,
              assert_type=options.assert_type,
              block_size=int(options.block_size),
              allow_unhashed=options.allow_unhashed)
        finally:
          if do_close_report_file:
            report_file.close()

      # Trace blocks.
      if options.root_block is not None:
        payload.TraceBlock(options.root_block, options.skip, sys.stdout, False)
      if options.kern_block is not None:
        payload.TraceBlock(options.kern_block, options.skip, sys.stdout, True)

      # Apply payload.
      if extra_args:
        if options.assert_type == _TYPE_FULL:
          payload.Apply(extra_args[0], extra_args[1])
        elif options.assert_type == _TYPE_DELTA:
          payload.Apply(extra_args[0], extra_args[1],
                        src_kernel_part=extra_args[2],
                        src_rootfs_part=extra_args[3])
        else:
          assert False, 'cannot get here'

    except update_payload.PayloadError, e:
      sys.stderr.write('Error: %s\n' % e)
      return 1

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
