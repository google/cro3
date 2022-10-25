#!/bin/bash
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

# Enter project GOPATH.
SCRIPT_DIR="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"
export PROJECT_GOPATH="${SCRIPT_DIR}/go"
export GOPATH="${PROJECT_GOPATH}"
export GO111MODULE=on
