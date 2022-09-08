#!/bin/bash
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

# Build go project.
SCRIPT_DIR="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"
source "${SCRIPT_DIR}/enter_gopath.sh"
CMD_PATH="${PROJECT_GOPATH}/bin/labtunnel"
cd "${PROJECT_GOPATH}/src" && go build -o "${CMD_PATH}"
echo "Successfully built labtunnel at '${CMD_PATH}'"
