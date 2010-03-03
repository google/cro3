# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os
import web
from datetime import datetime
import time 

class BuildObject:
  """
    Common base class that defines key paths in the source tree.
  """
  def __init__(self, root_dir, static_dir):
    self.app_id = "87efface-864d-49a5-9bb3-4b050a7c227a"
    self.root_dir = root_dir
    self.scripts_dir = "%s/scripts" % self.root_dir
    self.static_dir = static_dir
    self.x86_pkg_dir = "%s/build/x86/local_packages" % self.root_dir

  def AssertSystemCallSuccess(self, err, cmd="unknown"):
    """
      TODO(rtc): This code should probably live somewhere else.
    """
    if err != 0:
      raise Exception("%s failed to execute" % cmd)
