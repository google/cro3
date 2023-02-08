#!/bin/bash
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Show commands being run.
set -x

# Exit if any command exits non-zero.
set -e

# cd to the directory containing this script.
cd "$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"

export PYTHONPATH="${PWD}"

# Run pytest.
pytest -v

# Do a dry run of the service spawner to validate the YAML config.
./service_spawner.py --dry-run >/dev/null

# Check for formatting issues (also reports during pre-upload).
cros lint .
cros format --check .
