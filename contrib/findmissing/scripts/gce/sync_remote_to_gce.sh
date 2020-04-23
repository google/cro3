#!/bin/bash
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# Script transfers latest pulled findmissing changes into workdirectory
# Note: to see test results, restart web server by ssh'ing into the instance.

FINDMISSING_DIR=$(cd $(dirname $0)/../..; pwd)
cd "${FINDMISSING_DIR}"

# navigate to dev-util git directory and pull latest changes
git -C /opt/dev-util pull

# Replaces last running webserver code with latest pulled changes
# Note that we are not deleting the large linux git repositories (linux_*)
rsync -cav --exclude=".*" \
  "/opt/dev-util/contrib/findmissing/" "${FINDMISSING_DIR}" --delete
