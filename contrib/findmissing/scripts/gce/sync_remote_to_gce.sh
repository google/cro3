#!/bin/bash
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# Script transfers latest pulled findmissing changes into workdirectory
# Note: to see test results, restart web server by ssh'ing into the instance.

# navigate to dev-util git directory and pull latest changes
git -C /opt/dev-util pull

# Replaces last running webserver code with latest pulled changes
# Note that we are not deleting the large linux git repositories (linux_*)
rsync -O -avu \
  --exclude=".*" --exclude=secrets/ --exclude=env/ \
  --exclude=kernel_repositories/ --exclude=logs/ --delete \
  "/opt/dev-util/contrib/findmissing/" "/home/chromeos_patches"