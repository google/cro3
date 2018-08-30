# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script generate monarch metrics from Gs Cache server logs.

It parses the Nginx access log file of Gs Cache, e.g.
/var/log/nginx/gs-cache-server.access.log, and generate monarch metrics for Gs
Cache performance.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import argparse
import re
import sys
from logging import handlers

from chromite.lib import cros_logging as logging
from chromite.lib import metrics
from chromite.lib import ts_mon_config

_LOG_ROTATION_TIME = 'H'
_LOG_ROTATION_INTERVAL = 24  # hours
_LOG_ROTATION_BACKUP = 14  # Keep for 14 days.

_METRIC_NAME = 'chromeos/gs_cache/nginx/response'

# An example Nginx access log line is:
# <ip> 2018-07-26T18:13:49-07:00 "GET URL HTTP/1.1" 200 <size> "<agent>" HIT
_SUCCESS_RESPONSE_MATCHER = re.compile(
    r'^(?P<ip_addr>\d+\.\d+\.\d+\.\d+) '
    r'(?P<timestamp>\d+\-\d+\-\d+T\d+:\d+:\d+[+\-]\d+:\d+) '
    r'"GET (?P<url_path>\S*)[^"]*" '
    r'2\d\d (?P<size>\S+) "[^"]+" (?P<cache_status>\S+)')

# The format of URL is like:
#   /$ACTION/$BUCKET/$BUILD/$MILESTONE-$VERSION/$FILENAME?params
# We want ACTION, BUCKET, BUILD, MILESTONE, and FILENAME.
_URL_PATH_MATCHER = re.compile(
    r'^/(?P<action>[^/]+)/(?P<bucket>[^/]+)/(?P<build>[^/]+)/'
    r'(?P<milestone>\S+)\-(?P<version>[^/]+)/(?P<filename>[^\?]+)'
)


def emit_successful_response_metric(m):
  """Emit a Counter metric for a successful response.

  We parse the response line and uploads the size of response to a cumulative
  metric. Especially, the metric has a designate field of 'cache' which
  indicates the upstream cache status, e.g. HIT/MISS etc. For all list of cache
  status, see
  http://nginx.org/en/docs/http/ngx_http_upstream_module.html#var_upstream_cache_status

  Args:
    m: A regex match object or None.
  """
  if not m:
    return

  # Ignore all loopback calls between gs_archive_server and Nginx.
  if m.group('ip_addr') == '127.0.0.1':
    return

  logging.debug('Emitting successful response metric.')
  metric_fields = {
      'cache': m.group('cache_status'),
      'action': '',
      'bucket': '',
      'build': '',
      'milestone': '',
      'version': '',
      'endpoint': '',
  }
  requested_file_info = _URL_PATH_MATCHER.match(m.group('url_path'))
  if requested_file_info:
    metric_fields.update({
        'action': requested_file_info.group('action'),
        'bucket': requested_file_info.group('bucket'),
        'build': requested_file_info.group('build'),
        'milestone': requested_file_info.group('milestone'),
        'version': requested_file_info.group('version'),
        'endpoint': requested_file_info.group('filename'),
    })
  metrics.Counter(_METRIC_NAME).increment_by(int(m.group('size')),
                                             fields=metric_fields)


def input_log_file_type(filename):
  """A argparse type function converting input filename to file object.

  It converts '-' to sys.stdin.
  """
  if filename == '-':
    return sys.stdin
  return argparse.FileType('r')(filename)


def parse_args(argv):
  """Parses command line arguments."""
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument(
      "-i", "--input-log-file", metavar='NGINX_ACCESS_LOG_FILE',
      dest='input_fd', required=True,
      type=input_log_file_type,
      help=("Nginx log file of Gs Cache "
            "(use '-' to indicate reading from sys.stdin).")
  )
  parser.add_argument(
      "-l", "--log-file", default=sys.stdout,
      help="Log file of this script (default is sys.stdout)."
  )
  return parser.parse_args(argv)


def main(argv):
  """Main function."""
  args = parse_args(argv)

  logger = logging.getLogger()
  if args.log_file is sys.stdout:
    logger.addHandler(logging.StreamHandler(stream=sys.stdout))
  else:
    logger.addHandler(handlers.TimedRotatingFileHandler(
        args.log_file, when=_LOG_ROTATION_TIME,
        interval=_LOG_ROTATION_INTERVAL,
        backupCount=_LOG_ROTATION_BACKUP))
  logger.setLevel(logging.DEBUG)

  with ts_mon_config.SetupTsMonGlobalState('gs_cache_nginx_log_metrics',
                                           indirect=True):
    for line in args.input_fd:
      logging.debug('Parsing line: %s', line.strip())
      emit_successful_response_metric(_SUCCESS_RESPONSE_MATCHER.match(line))


if __name__ == "__main__":
  sys.exit(main(sys.argv[1:]))
