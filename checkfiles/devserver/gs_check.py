# Copyright 2015 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Google Storage health checks for devserver."""

from __future__ import print_function

import netifaces
import os
import ConfigParser

from chromite.lib import cros_build_lib


GLOBAL_CONFIG = '/usr/local/autotest/global_config.ini'
MOBLAB_CONFIG = '/usr/local/autotest/moblab_config.ini'
SHADOW_CONFIG = '/usr/local/autotest/shadow_config.ini'

GSUTIL_TIMEOUT_SEC = 5
GSUTIL_USER = 'moblab'
GSUTIL_INTERNAL_BUCKETS = ['gs://chromeos-image-archive']
MOBLAB_SUBNET_ADDR = '192.168.231.1'


def GetIp():
  for iface in netifaces.interfaces():
    if 'eth' not in iface:
      continue
    addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET)
    if not addrs:
      continue
    for addr in addrs:
      if MOBLAB_SUBNET_ADDR != addr.get('addr'):
        return addr['addr']

  return 'localhost'


class GsBucket(object):
  """Verify that we have access to the correct Google Storage bucket."""

  def __init__(self):
    self.bucket = None

  def BucketReachable(self, gs_url):
    """Check if we can reach the image server.

    Args:
      gs_url: The url of the Google Storage image server.

    Returns:
      True if |gs_url| can be reached.
      False otherwise.
    """
    # If our boto key is non-existent or is not configured correctly
    # for access to the right bucket, this check may take ~45 seconds.
    # This really ruins the monitor's performance as we do not yet
    # intelligently handle long running checks.
    #
    # Additionally, we cannot use chromite's timeout_util as it is
    # based on Python's signal module, which cannot be used outside
    # of the main thread. These checks are executed in a separate
    # thread handled by the monitor.
    #
    # To handle this, we rely on the linux utility 'timeout' and
    # forcefully kill our gsutil invocation if it is taking too long.

    cmd = ['timeout', '-s', '9', str(GSUTIL_TIMEOUT_SEC),
           'gsutil', 'ls', '-b', gs_url]
    try:
      cros_build_lib.SudoRunCommand(cmd, user=GSUTIL_USER)
    except cros_build_lib.RunCommandError:
      return False

    return True

  def Check(self):
    """Verifies Google storage bucket access.

    Returns:
      0 if we can access the correct bucket for our given Boto key.
      -1 if a configuration file could not be found.
      -2 if the configuration files did not contain the appropriate
        information.
    """
    config_files = [GLOBAL_CONFIG, MOBLAB_CONFIG, SHADOW_CONFIG]
    for f in config_files:
      if not os.path.exists(f):
        return -1

    config = ConfigParser.ConfigParser()
    config.read(config_files)

    gs_url = None

    for section in config.sections():
      for option, value in config.items(section):
        if 'image_storage_server' == option:
          gs_url = value
          break

    if not (gs_url and self.BucketReachable(gs_url)):
      self.bucket = gs_url
      return -2

    if gs_url in GSUTIL_INTERNAL_BUCKETS:
      self.bucket = gs_url
      return 1

    return 0

  def Diagnose(self, errcode):
    if 1 == errcode:
      return ('Using an internal Google Storage bucket %s' % self.bucket, [])

    elif -1 == errcode:
      return ('An autotest configuration file is missing.', [])

    elif -2 == errcode:
      return ('Moblab is not configured to access Google Storage.'
              ' The current bucket name is set to %s. Please'
              ' navigate to http://%s/moblab_setup/ and update'
              ' the image_storage_server variable. For more information,'
              ' please see https://www.chromium.org/chromium-os/testing/'
              'moblab/setup#TOC-Setting-up-the-boto-key-for-partners' % (
                  self.bucket, GetIp()), [])

    return ('Unknown error reached with error code: %s' % errcode, [])
