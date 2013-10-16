# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing gsutil helper methods."""

import distutils.version
import fnmatch
import os
import random
import re
import subprocess
import time

import devserver_constants
import log_util


GSUTIL_ATTEMPTS = 1
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

  Args:
    cmd: a string containing the gsutil command to run.
    err_msg: string prepended to the exception thrown in case of a failure.
  Returns:
    stdout of the called gsutil command.
  Raises:
    GSUtilError: if all attempts to run gsutil have failed.
  """
  proc = None
  sleep_timeout = 1
  stderr = None
  for _ in range(GSUTIL_ATTEMPTS):
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

  Args:
    src: source file on GS that needs to be downloaded.
    dst: file to copy the source file to.
  Raises:
    GSUtilError: if an error occurs during the download.
  """
  cmd = 'gsutil cp %s %s' % (src, dst)
  msg = 'Failed to download "%s".' % src
  GSUtilRun(cmd, msg)


def _GlobHasWildcards(pattern):
  """Returns True if a glob pattern contains any wildcards."""
  return len(pattern) > len(pattern.translate(None, '*?[]'))


def GetGSNamesWithWait(pattern, archive_url, err_str, timeout=600, delay=10,
                       is_regex_pattern=False):
  """Returns the google storage names specified by the given pattern.

  This method polls Google Storage until the target artifacts specified by the
  pattern is available or until the timeout occurs. Because we may not know the
  exact name of the target artifacts, the method accepts a filename pattern,
  to identify whether an artifact whose name matches the pattern exists (e.g.
  use pattern '*_full_*' to search for the full payload
  'chromeos_R17-1413.0.0-a1_x86-mario_full_dev.bin'). Returns the name only if
  found before the timeout.

  Args:
    pattern: a path pattern (glob or regex) identifying the files we need.
    archive_url: URL of the Google Storage bucket.
    err_str: String to display in the error message on error.
    timeout: how long are we allowed to keep trying.
    delay: how long to wait between attempts.
    is_regex_pattern: Whether the pattern is a regex (otherwise a glob).
  Returns:
    The list of artifacts matching the pattern in Google Storage bucket or None
    if not found.

  """
  # Define the different methods used for obtaining the list of files on the
  # archive directory, in the order in which they are attempted. Each method is
  # defined by a tuple consisting of (i) the gsutil command-line to be
  # executed; (ii) the error message to use in case of a failure (returned in
  # the corresponding exception); (iii) the desired return value to use in case
  # of success, or None if the actual command output should be used.
  get_methods = []
  # If the pattern is a glob and contains no wildcards, we'll first attempt to
  # stat the file via du.
  if not (is_regex_pattern or _GlobHasWildcards(pattern)):
    get_methods.append(('gsutil du %s/%s' % (archive_url, pattern),
                        'Failed to du on the artifact file.',
                        pattern))

  # The default method is to check the manifest file in the archive directory.
  get_methods.append(('gsutil cat %s/%s' % (archive_url, UPLOADED_LIST),
                      'Failed to get a list of uploaded files.',
                      None))
  # For backward compatibility, we fall back to using "gsutil ls" when the
  # manifest file is not present.
  get_methods.append(('gsutil ls %s/*' % archive_url,
                      'Failed to list archive directory contents.',
                      None))

  deadline = time.time() + timeout
  while True:
    uploaded_list = []
    for cmd, msg, override_result in get_methods:
      try:
        result = GSUtilRun(cmd, msg)
      except GSUtilError:
        continue  # It didn't work, try the next method.

      if override_result:
        result = override_result

      # Make sure we're dealing with artifact base names only.
      uploaded_list = [os.path.basename(p) for p in result.splitlines()]
      break

    # Only keep files matching the target artifact name/pattern.
    if is_regex_pattern:
      filter_re = re.compile(pattern)
      matching_names = [f for f in uploaded_list
                        if filter_re.search(f) is not None]
    else:
      matching_names = fnmatch.filter(uploaded_list, pattern)

    if matching_names:
      return matching_names

    # Don't delay past deadline.
    to_delay = random.uniform(1.5 * delay, 2.5 * delay)
    if to_delay < (deadline - time.time()):
      _Log('Retrying in %f seconds...%s', to_delay, err_str)
      time.sleep(to_delay)
    else:
      return None


def GetLatestVersionFromGSDir(gsutil_dir, with_release=True):
  """Returns most recent version number found in a GS directory.

  This lists out the contents of the given GS bucket or regex to GS buckets,
  and tries to grab the newest version found in the directory names.

  Args:
    gsutil_dir: directory location on GS to check.
    with_release: whether versions include a release milestone (e.g. R12).
  Returns:
    The most recent version number found.

  """
  cmd = 'gsutil ls %s' % gsutil_dir
  msg = 'Failed to find most recent builds at %s' % gsutil_dir
  dir_names = [p.split('/')[-2] for p in GSUtilRun(cmd, msg).splitlines()]
  try:
    filter_re = re.compile(devserver_constants.VERSION_RE if with_release
                           else devserver_constants.VERSION)
    versions = filter(filter_re.match, dir_names)
    latest_version = max(versions, key=distutils.version.LooseVersion)
  except ValueError:
    raise GSUtilError(msg)

  return latest_version
