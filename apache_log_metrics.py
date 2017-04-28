#!/usr/bin/env python2

# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to upload metrics from apache logs to Monarch.

We are interested in static file bandwidth, so it parses out GET requests to
/static and uploads the sizes to a cumulative metric.
"""
from __future__ import print_function

import argparse
import re
import sys

# TODO(ayatane): Fix cros lint pylint to work with virtualenv imports
# pylint: disable=import-error
from devserver_lib.devserver import MakeLogHandler

# only import setup_chromite before chromite import.
import setup_chromite # pylint: disable=unused-import
from chromite.lib import ts_mon_config
from chromite.lib import metrics
from chromite.lib import cros_logging as logging
from infra_libs import ts_mon


STATIC_GET_MATCHER = re.compile(
    r'^(?P<ip_addr>\d+\.\d+\.\d+\.\d+) '
    r'.*GET /static/(?P<endpoint>\S*)[^"]*" '
    r'200 (?P<size>\S+) .*')

STATIC_GET_METRIC_NAME = 'chromeos/devserver/apache/static_response_size'


LAB_SUBNETS = (
    ("172.17.40.0", 22),
    ("100.107.160.0", 19),
    ("100.115.128.0", 17),
    ("100.115.254.126", 25),
    ("100.107.141.128", 25),
    ("172.27.212.0", 22),
    ("100.107.156.192", 26),
    ("172.22.29.0", 25),
    ("172.22.38.0", 23),
    ("100.107.224.0", 23),
    ("100.107.226.0", 25),
    ("100.107.126.0", 25),
)

def IPToNum(ip):
  """Returns the integer represented by an IPv4 string.

  Args:
    ip: An IPv4-formatted string.
  """
  return reduce(lambda seed, x: seed * 2**8 + int(x),
                ip.split('.'),
                0)


def MatchesSubnet(ip, base, mask):
  """Whether the ip string |ip| matches the subnet |base|, |mask|.

  Args:
    ip: An IPv4 string.
    base: An IPv4 string which is the lowest value in the subnet.
    mask: The number of bits which are not wildcards in the subnet.
  """
  ip_value = IPToNum(ip)
  base_value = IPToNum(base)
  mask = (2**mask - 1) << (32 - mask)
  return (ip_value & mask) == (base_value & mask)


def InLab(ip):
  """Whether |ip| is an IPv4 address which is in the ChromeOS Lab.

  Args:
    ip: An IPv4 address to be tested.
  """
  return any(MatchesSubnet(ip, base, mask)
             for (base, mask) in LAB_SUBNETS)


MILESTONE_PATTERN = re.compile(r'R\d+')

FILENAME_CONSTANTS = [
    'stateful.tgz',
    'client-autotest.tar.bz2',
    'chromiumos_test_image.bin',
    'autotest_server_package.tar.bz2',
]

FILENAME_PATTERNS = [(re.compile(s), s) for s in FILENAME_CONSTANTS] + [
    (re.compile(r'dep-.*\.bz2'), 'dep-*.bz2'),
    (re.compile(r'chromeos_.*_delta_test\.bin-.*'),
     'chromeos_*_delta_test.bin-*'),
    (re.compile(r'chromeos_.*_full_test\.bin-.*'),
     'chromeos_*_full_test.bin-*'),
    (re.compile(r'test-.*\.bz2'), 'test-*.bz2'),
    (re.compile(r'dep-.*\.bz2'), 'dep-*.bz2'),
]


def MatchAny(needle, patterns, default=''):
  for pattern, value in patterns:
    if pattern.match(needle):
      return value
  return default


def ParseStaticEndpoint(endpoint):
  """Parses a /static/.* URL path into build_config, milestone, and filename.

  Static endpoints are expected to be of the form
      /static/$BUILD_CONFIG/$MILESTONE-$VERSION/$FILENAME

  This function expects the '/static/' prefix to already be stripped off.

  Args:
    endpoint: A string which is the matched URL path after /static/
  """
  build_config, milestone, filename = [''] * 3
  try:
    parts = endpoint.split('/')
    build_config = parts[0]
    if len(parts) >= 2:
      version = parts[1]
      milestone = version[:version.index('-')]
      if not MILESTONE_PATTERN.match(milestone):
        milestone = ''
    if len(parts) >= 3:
      filename = MatchAny(parts[-1], FILENAME_PATTERNS)

  except IndexError as e:
    logging.debug('%s failed to parse. Caught %s' % (endpoint, str(e)))

  return build_config, milestone, filename


def EmitStaticRequestMetric(m):
  """Emits a Counter metric for sucessful GETs to /static endpoints.

  Args:
    m: A regex match object
  """
  build_config, milestone, filename = ParseStaticEndpoint(m.group('endpoint'))

  try:
    size = int(m.group('size'))
  except ValueError:  # Zero is represented by "-"
    size = 0

  metrics.Counter(STATIC_GET_METRIC_NAME).increment_by(
      size, fields={
          'build_config': build_config,
          'milestone': milestone,
          'in_lab': InLab(m.group('ip_addr')),
          'endpoint': filename})


def RunMatchers(stream, matchers):
  """Parses lines of |stream| using patterns and emitters from |matchers|

  Args:
    stream: A file object to read from.
    matchers: A list of pairs of (matcher, emitter), where matcher is a regex
              and emitter is a function called when the regex matches.
  """
  for line in iter(stream.readline, ''):
    for matcher, emitter in matchers:
      logging.debug('Emitting %s for input "%s"',
                    emitter.__name__, line.strip())
      m = matcher.match(line)
      if m:
        emitter(m)
  # The input might terminate if the log gets rotated. Make sure that Monarch
  # flushes any pending metrics before quitting.
  ts_mon.close()


# TODO(phobbs) add a matcher for all requests, not just static files.
MATCHERS = [
    (STATIC_GET_MATCHER, EmitStaticRequestMetric),
]


def ParseArgs():
  """Parses command line arguments."""
  p = argparse.ArgumentParser(
      description='Parses apache logs and emits metrics to Monarch')
  p.add_argument('--logfile', required=True)
  return p.parse_args()


def main():
  """Sets up logging and runs matchers against stdin"""
  args = ParseArgs()
  root = logging.getLogger()

  root.addHandler(MakeLogHandler(args.logfile))
  root.setLevel(logging.DEBUG)
  ts_mon_config.SetupTsMonGlobalState('devserver_apache_log_metrics')
  RunMatchers(sys.stdin, MATCHERS)


if __name__ == '__main__':
  main()
