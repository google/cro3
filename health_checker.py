# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""A cherrypy application to check devserver health status."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json
import os
import subprocess
import threading
import time

import cherrypy

import cros_update_progress
import log_util


def _Log(message, *args):
  """Module-local log function."""
  return log_util.LogWithTag('HEALTHCHECKER', message, *args)


try:
  import psutil
except ImportError:
  # Ignore psutil import failure. This is for backwards compatibility, so
  # "cros flash" can still update duts with build without psutil installed.
  # The reason is that, during cros flash, local devserver code is copied over
  # to DUT, and devserver will be running inside DUT to stage the build.
  _Log('Python module psutil is not installed, devserver load data will not be '
       'collected')
  psutil = None
except OSError as e:
  # Ignore error like following. psutil may not work properly in builder. Ignore
  # the error as load information of devserver is not used in builder.
  # OSError: [Errno 2] No such file or directory: '/dev/pts/0'
  _Log('psutil is failed to be imported, error: %s. devserver load data will '
       'not be collected.', e)
  psutil = None


# Number of seconds between the collection of disk and network IO counters.
STATS_INTERVAL = 10.0
_1G = 1000000000


def require_psutil():
  """Decorator for functions require psutil to run."""
  def deco_require_psutil(func):
    """Wrapper of the decorator function.

    Args:
      func: function to be called.
    """
    def func_require_psutil(*args, **kwargs):
      """Decorator for functions require psutil to run.

      If psutil is not installed, skip calling the function.

      Args:
        *args: arguments for function to be called.
        **kwargs: keyword arguments for function to be called.
      """
      if psutil:
        return func(*args, **kwargs)
      else:
        _Log('Python module psutil is not installed. Function call %s is '
             'skipped.' % func)
    return func_require_psutil
  return deco_require_psutil


def _get_process_count(process_cmd_pattern):
  """Get the count of processes that match the given command pattern.

  Args:
    process_cmd_pattern: The regex pattern of process command to match.

  Returns:
    The count of processes that match the given command pattern.
  """
  try:
    # Use Popen instead of check_output since the latter cannot run with old
    # python version (less than 2.7)
    proc = subprocess.Popen(
        ['pgrep', '-fc', process_cmd_pattern],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    cmd_output, cmd_error = proc.communicate()
    if cmd_error:
      _Log('Error happened when getting process count: %s' % cmd_error)

    return int(cmd_output)
  except subprocess.CalledProcessError:
    return 0


def get_config():
  """Get cherrypy config for this application."""
  return {
      '/': {
          # Automatically add trailing slash, i.e.
          # /check_health -> /check_health/.
          'tools.trailing_slash.on': False,
      }
  }


class Root(object):
  """Cherrypy Root class of the application."""
  def __init__(self, devserver, static_dir):
    self._static_dir = static_dir
    self._devserver = devserver

    # Cache of disk IO stats, a thread refresh the stats every 10 seconds.
    # lock is not used for these variables as the only thread writes to these
    # variables is _refresh_io_stats.
    self.disk_read_bytes_per_sec = 0
    self.disk_write_bytes_per_sec = 0
    # Cache of network IO stats.
    self.network_sent_bytes_per_sec = 0
    self.network_recv_bytes_per_sec = 0
    self._start_io_stat_thread()

  @require_psutil()
  def _get_io_stats(self):
    """Get the IO stats as a dictionary.

    Returns:
      A dictionary of IO stats collected by psutil.
    """
    return {'disk_read_bytes_per_second': self.disk_read_bytes_per_sec,
            'disk_write_bytes_per_second': self.disk_write_bytes_per_sec,
            'disk_total_bytes_per_second': (self.disk_read_bytes_per_sec +
                                            self.disk_write_bytes_per_sec),
            'network_sent_bytes_per_second': self.network_sent_bytes_per_sec,
            'network_recv_bytes_per_second': self.network_recv_bytes_per_sec,
            'network_total_bytes_per_second': (self.network_sent_bytes_per_sec +
                                               self.network_recv_bytes_per_sec),
            'cpu_percent': psutil.cpu_percent(), }

  @require_psutil()
  def _refresh_io_stats(self):
    """A call running in a thread to update IO stats periodically."""
    prev_disk_io_counters = psutil.disk_io_counters()
    prev_network_io_counters = psutil.net_io_counters()
    prev_read_time = time.time()
    while True:
      time.sleep(STATS_INTERVAL)
      now = time.time()
      interval = now - prev_read_time
      prev_read_time = now
      # Disk IO is for all disks.
      disk_io_counters = psutil.disk_io_counters()
      network_io_counters = psutil.net_io_counters()

      self.disk_read_bytes_per_sec = (
          disk_io_counters.read_bytes -
          prev_disk_io_counters.read_bytes) / interval
      self.disk_write_bytes_per_sec = (
          disk_io_counters.write_bytes -
          prev_disk_io_counters.write_bytes) / interval
      prev_disk_io_counters = disk_io_counters

      self.network_sent_bytes_per_sec = (
          network_io_counters.bytes_sent -
          prev_network_io_counters.bytes_sent) / interval
      self.network_recv_bytes_per_sec = (
          network_io_counters.bytes_recv -
          prev_network_io_counters.bytes_recv) / interval
      prev_network_io_counters = network_io_counters

  @require_psutil()
  def _start_io_stat_thread(self):
    """Start the thread to collect IO stats."""
    thread = threading.Thread(target=self._refresh_io_stats)
    thread.daemon = True
    thread.start()

  @cherrypy.expose
  def index(self):
    """Collect the health status of devserver to see if it's ready for staging.

    Returns:
      A JSON dictionary containing all or some of the following fields:
      free_disk (int):            free disk space in GB
      staging_thread_count (int): number of devserver threads currently staging
                                  an image
      apache_client_count (int): count of Apache processes.
      telemetry_test_count (int): count of telemetry tests.
      gsutil_count (int): count of gsutil processes.
    """
    # Get free disk space.
    stat = os.statvfs(self._static_dir)
    free_disk = stat.f_bsize * stat.f_bavail / _1G
    apache_client_count = _get_process_count('bin/apache2? -k start')
    telemetry_test_count = _get_process_count('python.*telemetry')
    gsutil_count = _get_process_count('gsutil')
    au_process_count = len(cros_update_progress.GetAllRunningAUProcess())

    health_data = {
        'free_disk': free_disk,
        'staging_thread_count': self._devserver.staging_thread_count,
        'apache_client_count': apache_client_count,
        'telemetry_test_count': telemetry_test_count,
        'gsutil_count': gsutil_count,
        'au_process_count': au_process_count,
    }
    health_data.update(self._get_io_stats() or {})

    return json.dumps(health_data)
