#!/bin/bash
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# NOTE: Use this script for testing local findmissing modifications
# Script copies local findmissing changes to GCE web server directory
# To see test results, restart web server by ssh'ing into the instance.

# Script will not work if run from chroot environment


FINDMISSING_DIR=~/chromiumos/src/platform/dev/contrib/findmissing/
if [[ -n "$1" ]]; then
  FINDMISSING_DIR=$1
fi

if [[ -z "${GCE_EXTERNAL_IP}" ]]; then
  echo "ERROR: 'export GCE_EXTERNAL_IP=<...>' to define the GCE instances external ip."
  exit 1
fi

rsync -O -rltvz \
  --exclude=".*" --exclude=secrets/ \
  --exclude=kernel_repositories/ --exclude=logs/ --delete \
  "${FINDMISSING_DIR}" chromeos_patches@"${GCE_EXTERNAL_IP}":/home/chromeos_patches
