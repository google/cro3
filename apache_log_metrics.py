#!/usr/bin/python2

# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Script to upload metrics from apache logs to Monarch.

We are interested in static file bandwidth, so it parses out GET requests to
/static and uploads the sizes to a cumulative metric.
"""
from __future__ import print_function

import argparse
import logging
import re
import sys

from devserver import MakeLogHandler

from chromite.lib import ts_mon_config
from chromite.lib import metrics
from infra_libs import ts_mon


STATIC_GET_MATCHER = re.compile(
    r'^(?P<ip_addr>\d+\.\d+\.\d+\.\d+) '
    r'.*GET /static/\S*[^"]*" '
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
  return reduce(lambda seed, x: seed * 2**8 + int(x), ip.split('.'), 0)


def MatchesSubnet(ip, base, mask):
  ip_value = IPToNum(ip)
  base_value = IPToNum(base)
  mask = (2**mask - 1) << (32 - mask)
  return (ip_value & mask) == (base_value & mask)


def InLab(ip):
  return any(MatchesSubnet(ip, base, mask)
             for (base, mask) in LAB_SUBNETS)


def EmitStaticRequestMetric(m):
  """Emits a Counter metric for sucessful GETs to /static endpoints."""
  ipaddr, size = m.groups()
  try:
    size = int(size)
  except ValueError:  # Zero is represented by "-"
    size = 0

  metrics.Counter(STATIC_GET_METRIC_NAME).increment_by(
      size, fields={
          'builder': '',
          'in_lab': InLab(ipaddr),
          'endpoint': ''})


def RunMatchers(stream, matchers):
  """Parses lines of |stream| using patterns and emitters from |matchers|"""
  for line in stream:
    for matcher, emitter in matchers:
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
  p.add_argument('--logfile')
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
