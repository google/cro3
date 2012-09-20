# Copyright (c) 2009-2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os, sys

class BuildObject(object):
  """
    Common base class that defines key paths in the source tree.
  """
  def __init__(self, root_dir, static_dir):
    self.app_id = '87efface-864d-49a5-9bb3-4b050a7c227a'
    self.root_dir = root_dir
    self.devserver_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    self.static_dir = static_dir
    self.x86_pkg_dir = '%s/build/x86/local_packages' % self.root_dir
    try:
      self.scripts_dir = '%s/src/scripts' % os.environ['CROS_WORKON_SRCROOT']
    except KeyError:
      # Outside of chroot: This is a corner case. Since we live either in
      # platform/dev or /usr/bin/, scripts have to live in ../../../src/scripts
      self.scripts_dir = os.path.abspath(os.path.join(
          self.devserver_dir, '../../../src/scripts'))

  def AssertSystemCallSuccess(self, err, cmd='unknown'):
    """
      TODO(rtc): This code should probably live somewhere else.
    """
    if err != 0:
      raise Exception('%s failed to execute' % cmd)
