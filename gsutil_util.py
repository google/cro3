# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing gsutil helper methods."""

import distutils.version
import logging
import random
import re
import subprocess
import time

import devserver_constants
import log_util


GSUTIL_ATTEMPTS = 5
UPLOADED_LIST = 'UPLOADED'


# Module-local log function.
def _Log(message, *args):
  return log_util.LogWithTag('GSUTIL_UTIL', message, *args)


class GSUtilError(Exception):
  """Exception raised when we run into an error running gsutil."""
  pass


class PatternNotSpecific(Exception):
  """Raised when unexpectedly more than one item is returned for a pattern."""
  pass


def GSUtilRun(cmd, err_msg):
  """Runs a GSUTIL command up to GSUTIL_ATTEMPTS number of times.

  Attempts are tried with exponential backoff.

  Returns:
    stdout of the called gsutil command.
  Raises:
    subprocess.CalledProcessError if all attempt to run gsutil cmd fails.
  """
  proc = None
  sleep_timeout = 1
  stderr = None
  for _attempt in range(GSUTIL_ATTEMPTS):
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    if proc.returncode == 0:
      return stdout
    elif stderr and ('matched no objects' in stderr or
                     'non-existent object' in stderr):
      # TODO(sosa): Note this is a heuristic that makes us not re-attempt
      # unnecessarily. However, if it fails, the worst that can happen is just
      # waiting longer than necessary.
      break
    elif proc.returncode == 127:
      raise GSUtilError('gsutil tool not found in your path.')

    time.sleep(sleep_timeout)
    sleep_timeout *= 2

  raise GSUtilError('%s GSUTIL cmd %s failed with return code %d:\n\n%s' % (
      err_msg, cmd, proc.returncode, stderr))


def DownloadFromGS(src, dst):
  """Downloads object from gs_url |src| to |dst|.

  Raises:
    GSUtilError: if an error occurs during the download.
  """
  cmd = 'gsutil cp %s %s' % (src, dst)
  msg = 'Failed to download "%s".' % src
  GSUtilRun(cmd, msg)


def _GetGSNamesFromList(filename_list, pattern):
  """Given a list of filenames, returns the filenames that match pattern."""
  matches = []
  re_pattern = re.compile(pattern)
  for filename in filename_list:
    if re_pattern.match(filename):
      matches.append(filename)

  return matches


def GetGSNamesWithWait(pattern, archive_url, err_str, single_item=True,
                       timeout=600, delay=10):
  """Returns the google storage names specified by the given pattern.

  This method polls Google Storage until the target artifacts specified by the
  pattern is available or until the timeout occurs. Because we may not know the
  exact name of the target artifacts, the method accepts a filename pattern,
  to identify whether an artifact whose name matches the pattern exists (e.g.
  use pattern '_full_' to search for the full payload
  'chromeos_R17-1413.0.0-a1_x86-mario_full_dev.bin'). Returns the name only if
  found before the timeout.

  Args:
    pattern: Regular expression pattern to identify the target artifact.
    archive_url: URL of the Google Storage bucket.
    err_str: String to display in the error message on error.
    single_item: Only a single item should be returned. If more than one item
                 matches the pattern errors out unless pattern matches one
                 exactly.
    timeout/delay: optional and self-explanatory.

  Returns:
    The list of artifacts matching the pattern in Google Storage bucket or None
      if not found.

  Raises:
    PatternNotSpecific: If caller sets single_item but multiple items match.
  """
  deadline = time.time() + timeout
  while True:
    uploaded_list = []
    try:
      cmd = 'gsutil cat %s/%s' % (archive_url, UPLOADED_LIST)
      msg = 'Failed to get a list of uploaded files.'
      uploaded_list = GSUtilRun(cmd, msg).splitlines()
    except GSUtilError:
      # For backward compatibility, falling back to use "gsutil ls"
      # when the manifest file is not present.
      cmd = 'gsutil ls %s/*' % archive_url
      msg = 'Failed to list payloads.'
      returned_list = GSUtilRun(cmd, msg).splitlines()
      for item in returned_list:
        try:
          uploaded_list.append(item.rsplit('/', 1)[1])
        except IndexError:
          pass

    # Check if all target artifacts are available.
    found_names = _GetGSNamesFromList(uploaded_list, pattern)
    if found_names:
      if single_item and len(found_names) > 1:
        found_names_exact = _GetGSNamesFromList(uploaded_list, '^%s$' % pattern)
        if not found_names_exact:
          raise PatternNotSpecific(
            'Too many items %s returned by pattern %s in %s' % (
                str(found_names), pattern, archive_url))
        else:
          logging.info('More than one item returned but one file matched'
                       ' exactly so returning that: %s.', found_names_exact)
          found_names = found_names_exact

      return found_names

    # Don't delay past deadline.
    to_delay = random.uniform(1.5 * delay, 2.5 * delay)
    if to_delay < (deadline - time.time()):
      _Log('Retrying in %f seconds...%s', to_delay, err_str)
      time.sleep(to_delay)
    else:
      return None


def GetLatestVersionFromGSDir(gsutil_dir):
  """Returns most recent version number found in a GS directory.

  This lists out the contents of the given GS bucket or regex to GS buckets,
  and tries to grab the newest version found in the directory names.
  """
  cmd = 'gsutil ls %s' % gsutil_dir
  msg = 'Failed to find most recent builds at %s' % gsutil_dir
  dir_names = [p.split('/')[-2] for p in GSUtilRun(cmd, msg).splitlines()]
  try:
    versions = filter(lambda x: re.match(devserver_constants.VERSION_RE, x),
                      dir_names)
    latest_version = max(versions, key=distutils.version.LooseVersion)
  except ValueError:
    raise GSUtilError(msg)

  return latest_version
