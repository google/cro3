# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import os

def GetPackages():
  """
    Lists all of the packages that can be built with a make_pkg.sh script.
  """
  pkgs = [] 
  cli = os.popen("find %s -name make_pkg.sh" % root_dir).read().split('\n')
  for pkg in cli:
    if pkg == "":
      continue
    pkg_name = pkg.split('/')[-2]
    web.debug(pkg_name)
    li.append(pkg_name)

