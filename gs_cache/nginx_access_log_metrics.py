# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This script generate monarch metrics from Gs Cache server logs.

It parses the Nginx access log file of Gs Cache, e.g.
/var/log/nginx/gs-cache-server.access.log, and generate monarch metrics for Gs
Cache performance.
"""

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

_METRIC_NAME = 'chromeos/gs_cache/nginx/response_metrics'

# An example Nginx access log line is:
# <ip> 2018-07-26T18:13:49-07:00 "GET URL HTTP/1.1" 200 <size> "<agent>" HIT
_SUCCESS_RESPONSE_MATCHER = re.compile(
    r'^(?P<ip_addr>\d+\.\d+\.\d+\.\d+) '
    r'(?P<timestamp>\d+\-\d+\-\d+T\d+:\d+:\d+[+\-]\d+:\d+) '
    r'"(?P<http_method>\S+) (?P<url_path>\S*)[^"]*" '
    r'(?P<status_code>\d+) (?P<size>\S+) "[^"]+" (?P<cache_status>\S+)')

# Define common regexes.
_COMMON_PARTIAL_REGEX = (r'(?P<build>[^/]+)/(?P<milestone>\S\d+)'
                         r'\-(?P<version>[^/]+)')
_COMMON_FULL_REGEX = (r'^/(?P<action>[^/]+)/(?P<bucket>[^/]+)/%s' %
                      _COMMON_PARTIAL_REGEX)

# Regex for all accepted actions.
_URL_PATH_MATCHER = {
    'decompress': re.compile(r'%s/(?P<filename>[^\?]+)' % _COMMON_FULL_REGEX),
    'download': re.compile(r'%s/(?P<filename>[^\?]+)' % _COMMON_FULL_REGEX),
    'extract': re.compile(r'%s/(?P<package>[^\?]+)\?file=(?P<filename>[^\?]+)'
                          % _COMMON_FULL_REGEX),
    'list_dir': re.compile(r'%s' % _COMMON_FULL_REGEX),

    # TODO(crbug.com/1122319): Remove all fake RPCs once all devserver clients
    # have been migrated to TLW/TLS caching API.

    'fake_check_health': re.compile(r'/(?P<action>[^/]+)'),
    'fake_list_image_dir': re.compile(r'/(?P<action>[^/]+)'),
    'fake_is_staged': re.compile(r'/(?P<action>[^/]+)'),
    'fake_stage': re.compile(r'/(?P<action>[^/]+)'),
    'setup_telemetry': re.compile(r'/(?P<action>[^/]+)\?archive_url=gs://'
                                  r'(?P<bucket>[^/]+)/%s' %
                                  _COMMON_PARTIAL_REGEX),
    'static': re.compile(r'/(?P<action>[^/]+)/(?P<filename>[^\?]+)'),
    'update': re.compile(r'^/(?P<action>[^/]+)/%s.*' % _COMMON_PARTIAL_REGEX),
}


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

  logging.debug('Emitting successful response metric.')
  metric_fields = {
      'cache': m.group('cache_status'),
      'action': '',
      'bucket': '',
      'build': '',
      'milestone': '',
      'endpoint': '',
      'status_code': m.group('status_code'),
  }
  metric_fields.update(match_url_path(m.group('url_path')))
  metrics.Counter(_METRIC_NAME).increment_by(int(m.group('size')),
                                             fields=metric_fields)


def match_url_path(url):
  """Extract information from the url by matching it with the appropriate regex.

  Args:
    url: The url to be matched.

  Returns:
    A dictionary containing all matched fields and their respective values.
  """
  # The url is either in the format /<action_name>?<param1>=<value1>.. or
  # /<action_name>/<arg1>/<arg2>/..?<param1>=<value1>..
  # To single out the action name from these urls, first strip the leading '/'
  # and then handle the cases where the action name can be followed by a '/'
  # or a '?'.
  action_name = url.strip('/').split('/')[0].split('?')[0]
  try:
    info = _URL_PATH_MATCHER[action_name].match(url)
    matched_group_dict = info.groupdict()
    return {
        'action': matched_group_dict.get('action', ''),
        'bucket': matched_group_dict.get('bucket', ''),
        'build': matched_group_dict.get('build', ''),
        'milestone': matched_group_dict.get('milestone', ''),
        'endpoint': matched_group_dict.get('filename', ''),
    }
  except KeyError:
    logging.warning('The URL: %s did not match with any of the regexes. May '
                    'be it is new?', url)
  except Exception as e:
    logging.error('Could not extract fields names for %s due to exception: %s',
                  url, e)
  return {}

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
      '-i', '--input-log-file', metavar='NGINX_ACCESS_LOG_FILE',
      dest='input_fd', required=True,
      type=input_log_file_type,
      help=('Nginx log file of Gs Cache '
            '(use "-" to indicate reading from sys.stdin).')
  )
  parser.add_argument(
      '-l', '--log-file', default=sys.stdout,
      help='Log file of this script (default is sys.stdout).'
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
    for line in iter(args.input_fd.readline, b''):
      logging.debug('Parsing line: %s', line.strip())
      emit_successful_response_metric(_SUCCESS_RESPONSE_MATCHER.match(line))


if __name__ == "__main__":  # pylint: disable=invalid-string-quote
  sys.exit(main(sys.argv[1:]))
