#!/usr/bin/env python3
# # -*- coding: utf-8 -*-
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Parse net.log"""

import argparse
import codecs
from datetime import datetime
import os
import re
import sys

assert sys.version_info >= (3, 6), 'This module requires Python 3.6+'

# Fix printing of unicode characters:
# http://go/py3-differences#the-print-function
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)

DATE_LENGTH = 11 # (i.e 2021-03-19T15:02:17.489679Z)
DATETIME_LENGTH = 27 # (i.e 2021-03-19T15:02:17.489679Z)
DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f'

TRANSLATED_SUBSTRING_SEARCH = (u'request (translated)',
                               u'response (translated)',
                               u'message (translated)',
                               u'indication (translated)')
RAW_SUBSTRING_SEARCH = (u' Sent message...',
                        u' Received message...')

RAW_SIGNAL_STRENGTH_SUBSTRING_SEARCH = (u'"Get Signal Strength"',
                                        u'"Get Signal Info"')


def parse_raw_message(line, mm_raw_parser_level):
  """Parses one raw message from Modemmanager"""
  line_parts = line.split(u'(translated)...', 1)
  parsed = u''
  useful_header_values = u''
  if len(line_parts) > 1:
    values = re.split(u'#012<<<<<<|#012>>>>>>', line_parts[1])
    pattern_found = False
    for value in values:
      if mm_raw_parser_level >= 3 and not pattern_found:
        if any(value.strip().startswith(x) for x in (u'type ',
                                                     u'transaction ')):
          useful_header_values += value  + u'\n'
        if value.strip().startswith('Contents:'): # only useful for MBIM
          pattern_found = True
          parsed = '\n' + useful_header_values

      if mm_raw_parser_level >= 3:
        # parse Qmi message
        if any(value.strip().startswith(x) for x in (
          'length ', 'value ','tlv_length ')):
          continue

      parsed += value  + u'\n'

  return line_parts[0] + parsed


datetime_re = re.compile(
  r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z')
def search_datetime(line):
  """Find the timestamp in the line and convert it as datetime type.

  :param dt_string: str, line to parse
  """
  dt = datetime_re.search(line)
  if dt:
    try:
      # unfortunately, datetime.fromisoformat is not supported on < python 3.7.
      # ChromeOS doesn't support dateutil either
      return datetime.strptime(dt.group().strip('Z'), DATETIME_FORMAT)
    except ValueError:
      return None
  return None


def parse_net_log(file_name, remove_date, process_filter, mm_raw_parser_level,
                add_seconds_counter, hide_date_time, hide_messages,
                hide_signal_messages):
  output = ''
  first_datetime = None
  time_diff_value = ''
  time_diff_pos = DATETIME_LENGTH
  if hide_date_time:
    time_diff_pos = 0
  elif remove_date:
    time_diff_pos = DATETIME_LENGTH - DATE_LENGTH

  # ISO-8859-1 seems to be the best encoding for net.log, since some
  # characters are not supported by utf-8.
  with open(file_name, encoding='ISO-8859-1') as ff:
    # pylint: disable=line-too-long
    process_re = re.compile(
      r'(?:(?<=DEBUG )|(?<=INFO )|(?<=WARNING )|(?<=NOTICE )|(?<=ERR )|(?<=CRIT ))(.*?)(?=\[[0-9]*\])')
    # pylint: enable=line-too-long
    for line in ff:
      line = line.strip()

      # Remove raw messages. We still keep the translated ones.
      if ((mm_raw_parser_level > 1 or hide_messages) and
        any(x in line for x in RAW_SUBSTRING_SEARCH)):
        continue

      if (hide_messages and any(x in line for x in TRANSLATED_SUBSTRING_SEARCH
                                                   + RAW_SUBSTRING_SEARCH)):
        continue

      if (hide_signal_messages and any(x in line for x in
                                       RAW_SIGNAL_STRENGTH_SUBSTRING_SEARCH)):
        continue

      if add_seconds_counter:
        if not first_datetime:
          first_datetime = search_datetime(line)
        current_timestamp = search_datetime(line)
        if first_datetime and current_timestamp:
          time_diff = current_timestamp - first_datetime
          time_diff_value = '{:011.6f}'.format(time_diff.total_seconds())
        else:
          time_diff_value = '-'*11

      if hide_date_time:
        line = line[DATETIME_LENGTH:]
      elif remove_date:
        line = line[DATE_LENGTH:]

      if add_seconds_counter:
        # The reason to put `time_diff_value` after the date, is that some UIs
        # used to visualize logs(i.e. lnav) depend on the datetime value to be
        # at position 0.
        line = (line[:time_diff_pos] + ' ' + time_diff_value
                + line[time_diff_pos:])

      process = process_re.search(line)
      if process:
        process = process.group()
      # Grep values only if values were provided
      if process_filter and process not in process_filter:
        continue

      if process:
        # Remove PID
        line = re.sub(r'{0}\[[0-9]*\]'.format(process), u' ' + process, line)

        # Remove logging level(i.e. DEBUG, INFO)
        line = re.sub(u'(DEBUG|INFO|WARNING|NOTICE)  {0}'.format(process),
                      process, line)

      if any([x in line for x in TRANSLATED_SUBSTRING_SEARCH]):
        if mm_raw_parser_level > 0:
          line = parse_raw_message(line, mm_raw_parser_level)

      output += line + '\n'

  print(output)

def parse_arguments(argv):
  """Parses command line arguments.

  Args:
    argv: List of commandline arguments.

  Returns:
    Namespace object containing parsed arguments.
  """
  parser = argparse.ArgumentParser(
      description=__doc__,
      formatter_class=argparse.RawTextHelpFormatter)

  parser.add_argument('--show-date', action='store_true',
                      default=False, help='Show `date` in timestamps.')
  parser.add_argument('--hide-date-time', '--hdt', action='store_true',
                      default=False, help='Hide `date-time` in all lines.')
  parser.add_argument('--hide-messages', '--hm', action='store_true',
                      default=False,
                      help='Hide all Sent and Received messages.')
  parser.add_argument('-p','--process', action='append',
                      help='Filter lines by process name.')

  parser.add_argument('--add-seconds-counter', '-s', action='store_true',
                      default=False, help='Add a timestamp that starts from 0'
                      ' at the time of the first log entry')

  parser.add_argument('--mm-raw-level', '-r', type=int, default=3,
                      help='Log level of the raw message.'
                           '\n0=No Parse'
                           '\n1=Parse and split lines'
                           '\n2=Previous option + remove raw values'
                           '\n3=Previous option + remove header')

  parser.add_argument('--hide-signal-messages', '--hsm', action='store_true',
                      default=False, help='Hide MM raw messages related to'
                                          'signal strength.')

  parser.add_argument('file_path', nargs='?', metavar='FILE',
                      default='/var/log/net.log',
                      help='The path to the `net.log` file to parse.')

  return parser.parse_args(argv[1:])

def main(argv):
  """Main function."""
  opts = parse_arguments(argv)

  parse_net_log(opts.file_path, not opts.show_date, opts.process,
              opts.mm_raw_level, opts.add_seconds_counter, opts.hide_date_time,
              opts.hide_messages, opts.hide_signal_messages)
  return os.EX_OK


if __name__ == '__main__':
  sys.exit(main(sys.argv))
