#!/usr/bin/python2
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Command-line tool for checking and applying Chrome OS update payloads."""

from __future__ import print_function

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


def ParseArguments(argv):
  """Parse and validate command-line arguments.

  Args:
    argv: command-line arguments to parse (excluding the program name)

  Returns:
    A tuple (opts, payload, extra_args), where `opts' are the options
    returned by the parser, `payload' is the name of the payload file
    (mandatory argument) and `extra_args' are any additional command-line
    arguments.
  """
  parser = optparse.OptionParser(
      usage=('Usage: %prog [OPTION...] PAYLOAD [DST_KERN DST_ROOT '
             '[SRC_KERN SRC_ROOT]]'),
      description=('Applies a Chrome OS update PAYLOAD to SRC_KERN and '
                   'SRC_ROOT emitting DST_KERN and DST_ROOT, respectively. '
                   'SRC_KERN and SRC_ROOT are only needed for delta payloads. '
                   'When no partitions are provided, verifies the payload '
                   'integrity.'),
      epilog=('Note: a payload may verify correctly but fail to apply, and '
              'vice versa; this is by design and can be thought of as static '
              'vs dynamic correctness. A payload that both verifies and '
              'applies correctly should be safe for use by the Chrome OS '
              'Update Engine. Use --check to verify a payload prior to '
              'applying it.'))

  check_opts = optparse.OptionGroup(parser, 'Checking payload integrity')
  check_opts.add_option('-c', '--check', action='store_true', default=False,
                        help=('force payload integrity check (e.g. before '
                              'applying)'))
  check_opts.add_option('-D', '--describe', action='store_true', default=False,
                        help='Print a friendly description of the payload.')
  check_opts.add_option('-r', '--report', metavar='FILE',
                        help="dump payload report (`-' for stdout)")
  check_opts.add_option('-t', '--type', metavar='TYPE', dest='assert_type',
                        help=("assert that payload is either `%s' or `%s'" %
                              (_TYPE_FULL, _TYPE_DELTA)))
  check_opts.add_option('-z', '--block-size', metavar='NUM', default=0,
                        type='int',
                        help='assert a non-default (4096) payload block size')
  check_opts.add_option('-u', '--allow-unhashed', action='store_true',
                        default=False, help='allow unhashed operations')
  check_opts.add_option('-d', '--disabled_tests', metavar='TESTLIST',
                        default=(),
                        help=('comma-separated list of tests to disable; '
                              'available values: ' +
                              ', '.join(update_payload.CHECKS_TO_DISABLE)))
  check_opts.add_option('-k', '--key', metavar='FILE',
                        help=('Override standard key used for signature '
                              'validation'))
  check_opts.add_option('-m', '--meta-sig', metavar='FILE',
                        help='verify metadata against its signature')
  check_opts.add_option('-p', '--root-part-size', metavar='NUM',
                        default=0, type='int',
                        help=('override rootfs partition size auto-inference'))
  check_opts.add_option('-P', '--kern-part-size', metavar='NUM',
                        default=0, type='int',
                        help=('override kernel partition size auto-inference'))
  parser.add_option_group(check_opts)

  trace_opts = optparse.OptionGroup(parser, 'Applying payload')
  trace_opts.add_option('-x', '--extract-bsdiff', action='store_true',
                        default=False,
                        help=('use temp input/output files with BSDIFF '
                              'operations (not in-place)'))
  trace_opts.add_option('--bspatch-path', metavar='FILE',
                        help=('use the specified bspatch binary'))
  parser.add_option_group(trace_opts)

  trace_opts = optparse.OptionGroup(parser, 'Block tracing')
  trace_opts.add_option('-b', '--root-block', metavar='BLOCK', type='int',
                        help='trace the origin for a rootfs block')
  trace_opts.add_option('-B', '--kern-block', metavar='BLOCK', type='int',
                        help='trace the origin for a kernel block')
  trace_opts.add_option('-s', '--skip', metavar='NUM', default='0', type='int',
                        help='skip first NUM occurrences of traced block')
  parser.add_option_group(trace_opts)

  # Parse command-line arguments.
  opts, args = parser.parse_args(argv)

  # Validate a value given to --type, if any.
  if opts.assert_type not in (None, _TYPE_FULL, _TYPE_DELTA):
    parser.error('invalid argument to --type: %s' % opts.assert_type)

  # Convert and validate --disabled_tests value list, if provided.
  if opts.disabled_tests:
    opts.disabled_tests = opts.disabled_tests.split(',')
    for test in opts.disabled_tests:
      if test not in update_payload.CHECKS_TO_DISABLE:
        parser.error('invalid argument to --disabled_tests: %s' % test)

  # Ensure consistent use of block tracing options.
  do_block_trace = not (opts.root_block is None and opts.kern_block is None)
  if opts.skip and not do_block_trace:
    parser.error('--skip must be used with either --root-block or --kern-block')

  # There are several options that imply --check.
  opts.check = (opts.check or opts.report or opts.assert_type or
                opts.block_size or opts.allow_unhashed or
                opts.disabled_tests or opts.meta_sig or opts.key or
                opts.root_part_size or opts.kern_part_size)

  # Check number of arguments, enforce payload type accordingly.
  if len(args) == 3:
    if opts.assert_type == _TYPE_DELTA:
      parser.error('%s payload requires source partition arguments' %
                   _TYPE_DELTA)
    opts.assert_type = _TYPE_FULL
  elif len(args) == 5:
    if opts.assert_type == _TYPE_FULL:
      parser.error('%s payload does not accept source partition arguments' %
                   _TYPE_FULL)
    opts.assert_type = _TYPE_DELTA
  elif len(args) == 1:
    # Not applying payload; if block tracing not requested either, do an
    # integrity check.
    if not do_block_trace:
      opts.check = True
    if opts.extract_bsdiff:
      parser.error('--extract-bsdiff can only be used when applying payloads')
    if opts.bspatch_path:
      parser.error('--bspatch-path can only be used when applying payloads')
  else:
    parser.error('unexpected number of arguments')

  # By default, look for a metadata-signature file with a name based on the name
  # of the payload we are checking. We only do it if check was triggered.
  if opts.check and not opts.meta_sig:
    default_meta_sig = args[0] + '.metadata-signature'
    if os.path.isfile(default_meta_sig):
      opts.meta_sig = default_meta_sig
      print('Using default metadata signature', opts.meta_sig, file=sys.stderr)

  return opts, args[0], args[1:]


def main(argv):
  # Parse and validate arguments.
  options, payload_file_name, extra_args = ParseArguments(argv[1:])

  with open(payload_file_name) as payload_file:
    payload = update_payload.Payload(payload_file)
    try:
      # Initialize payload.
      payload.Init()

      if options.describe:
        payload.Describe()

      # Perform payload integrity checks.
      if options.check:
        report_file = None
        do_close_report_file = False
        metadata_sig_file = None
        try:
          if options.report:
            if options.report == '-':
              report_file = sys.stdout
            else:
              report_file = open(options.report, 'w')
              do_close_report_file = True

          metadata_sig_file = options.meta_sig and open(options.meta_sig)
          payload.Check(
              pubkey_file_name=options.key,
              metadata_sig_file=metadata_sig_file,
              report_out_file=report_file,
              assert_type=options.assert_type,
              block_size=int(options.block_size),
              rootfs_part_size=options.root_part_size,
              kernel_part_size=options.kern_part_size,
              allow_unhashed=options.allow_unhashed,
              disabled_tests=options.disabled_tests)
        finally:
          if metadata_sig_file:
            metadata_sig_file.close()
          if do_close_report_file:
            report_file.close()

      # Trace blocks.
      if options.root_block is not None:
        payload.TraceBlock(options.root_block, options.skip, sys.stdout, False)
      if options.kern_block is not None:
        payload.TraceBlock(options.kern_block, options.skip, sys.stdout, True)

      # Apply payload.
      if extra_args:
        dargs = {'bsdiff_in_place': not options.extract_bsdiff}
        if options.bspatch_path:
          dargs['bspatch_path'] = options.bspatch_path
        if options.assert_type == _TYPE_DELTA:
          dargs['old_kernel_part'] = extra_args[2]
          dargs['old_rootfs_part'] = extra_args[3]

        payload.Apply(extra_args[0], extra_args[1], **dargs)

    except update_payload.PayloadError, e:
      sys.stderr.write('Error: %s\n' % e)
      return 1

  return 0


if __name__ == '__main__':
  sys.exit(main(sys.argv))
