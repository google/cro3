#!/bin/bash
#
# Copyright 2022 The ChromiumOS Authors.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


KERNEL_REPOS_DIR="${HOME}/findmissing_workspace/kernel_repositories"
LINUX_CHROME="${KERNEL_REPOS_DIR}/linux_chrome"
LOG_FILE="/var/log/findmissing/findmissing.log"

{
    echo "Triggered clean at $(date)"
    git -C "${LINUX_CHROME}" prune --expire=now --progress
    rm -f "${LINUX_CHROME}/.git/gc.log"
    echo "End of clean at $(date)"
} >> "${LOG_FILE}" 2>&1
