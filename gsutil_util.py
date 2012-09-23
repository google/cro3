# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing gsutil helper methods."""

import subprocess
import time


GSUTIL_ATTEMPTS = 5


class GSUtilError(Exception):
  """Exception raises when we run into an error running gsutil."""
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
  for _attempt in range(GSUTIL_ATTEMPTS):
    # Note processes can hang when capturing from stderr. This command
    # specifically doesn't pipe stderr.
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    stdout, _stderr = proc.communicate()
    if proc.returncode == 0:
      return stdout

    time.sleep(sleep_timeout)
    sleep_timeout *= 2

  else:
    raise GSUtilError('%s GSUTIL cmd %s failed with return code %d' % (
        err_msg, cmd, proc.returncode))


def DownloadFromGS(src, dst):
  """Downloads object from gs_url |src| to |dst|.

  Raises:
    GSUtilError: if an error occurs during the download.
  """
  cmd = 'gsutil cp %s %s' % (src, dst)
  msg = 'Failed to download "%s".' % src
  GSUtilRun(cmd, msg)
