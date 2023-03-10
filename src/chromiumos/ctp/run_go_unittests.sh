#!/bin/bash -e
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Run unit tests against a standardized go install. Meant for presubmit.

# Move to this script's directory.
script_dir="$(realpath "$(dirname "$0")")"
cd "${script_dir}"

# Get go from CIPD.
echo "Getting go from CIPD..."
cipd_root="${script_dir}/.cipd_bin"
cipd ensure \
  -log-level warning \
  -root "${cipd_root}" \
  -ensure-file - \
  <<ENSURE_FILE
infra/3pp/tools/go/\${platform} latest
ENSURE_FILE

PATH="${cipd_root}/bin:${PATH}"

echo "Running unittests..."
GOROOT="${cipd_root}" go test -mod=readonly ./...
