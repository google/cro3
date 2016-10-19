# Copyright (c) 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A progress class for tracking CrOS auto-update process.

This class is mainly designed for:
  1. Set the pattern for generating the filenames of
     track_status_file/execute_log_file.
     track_status_file: Used for record the current step of CrOS auto-update
                        process. Only has one line.
     execute_log_file: Used for record the whole logging info of the CrOS
                       auto-update process, including any debug information.
  2. Write current auto-update process into the track_status_file.
  3. Read current auto-update process from the track_status_file.

This file also offers external functions that are related to add/check/delete
the progress of the CrOS auto-update process.
"""

from __future__ import print_function

import glob
import logging
import os

# only import setup_chromite before chromite import.
import setup_chromite # pylint: disable=unused-import
try:
  from chromite.lib import osutils
except ImportError as e:
  logging.debug('chromite cannot be imported: %r', e)
  osutils = None

# Path for status tracking log.
_TRACK_LOG_FILE_PATH = '/tmp/auto-update/tracking_log/%s_%s.log'

# Path for executing log.
_EXECUTE_LOG_FILE_PATH = '/tmp/auto-update/executing_log/%s_%s.log'

# Path and files for temporarily saving devserver codes, devserver and
# update engine log.
_CROS_UPDATE_TEMP_PATH = '/tmp/cros-update_%s_%s'

# The string for update process finished
FINISHED = 'Completed'
ERROR_TAG = 'Error'


def ReadOneLine(filename):
  """Read one line from file.

  Args:
    filename: The file to be read.
  """
  return open(filename, 'r').readline().rstrip('\n')


def IsProcessAlive(pid):
  """Detect whether a process is alive or not.

  Args:
    pid: The process id.
  """
  path = '/proc/%s/stat' % pid
  try:
    stat = ReadOneLine(path)
  except IOError:
    if not os.path.exists(path):
      return False

    raise

  return stat.split()[2] != 'Z'


def GetExecuteLogFile(host_name, pid):
  """Return the whole path of execute log file."""
  if not os.path.exists(os.path.dirname(_EXECUTE_LOG_FILE_PATH)):
    osutils.SafeMakedirs(os.path.dirname(_EXECUTE_LOG_FILE_PATH))

  return _EXECUTE_LOG_FILE_PATH % (host_name, pid)


def GetTrackStatusFile(host_name, pid):
  """Return the whole path of track status file."""
  if not os.path.exists(os.path.dirname(_TRACK_LOG_FILE_PATH)):
    osutils.SafeMakedirs(os.path.dirname(_TRACK_LOG_FILE_PATH))

  return _TRACK_LOG_FILE_PATH % (host_name, pid)


def GetAllTrackStatusFileByHostName(host_name):
  """Return a list of existing track status files generated for a host."""
  return glob.glob(_TRACK_LOG_FILE_PATH % (host_name, '*'))


def GetAUTempDirectory(host_name, pid):
  """Return the temp dir for storing codes and logs during auto-update."""
  au_tempdir = _CROS_UPDATE_TEMP_PATH % (host_name, pid)
  if not os.path.exists(au_tempdir):
    osutils.SafeMakedirs(au_tempdir)

  return au_tempdir


def ReadExecuteLogFile(host_name, pid):
  """Return the content of execute log file."""
  return osutils.ReadFile(GetExecuteLogFile(host_name, pid))


def DelTrackStatusFile(host_name, pid):
  """Delete the track status log."""
  osutils.SafeUnlink(GetTrackStatusFile(host_name, pid))


def DelExecuteLogFile(host_name, pid):
  """Delete the track status log."""
  osutils.SafeUnlink(GetExecuteLogFile(host_name, pid))


def DelAUTempDirectory(host_name, pid):
  """Delete the directory including auto-update-related logs."""
  osutils.RmDir(GetAUTempDirectory(host_name, pid))


class AUProgress(object):
  """Used for tracking the CrOS auto-update progress."""

  def __init__(self, host_name, pid):
    """Initialize a CrOS update progress instance.

    Args:
      host_name: The name of host, should be in the file_name of the status
        tracking file of auto-update process.
      pid: The process id, should be in the file_name too.
    """
    self.host_name = host_name
    self.pid = pid

  @property
  def track_status_file(self):
    """The track status file to record the CrOS auto-update progress."""
    return GetTrackStatusFile(self.host_name, self.pid)

  def WriteStatus(self, content):
    """Write auto-update progress into status tracking file.

    Args:
      content: The content to be recorded.
    """
    if not self.track_status_file:
      return

    try:
      with open(self.track_status_file, 'w') as out_log:
        out_log.write(content)
    except Exception as e:
      logging.error('Cannot write au status: %r', e)

  def ReadStatus(self):
    """Read auto-update progress from status tracking file."""
    with open(self.track_status_file, 'r') as out_log:
      return out_log.read().rstrip('\n')
