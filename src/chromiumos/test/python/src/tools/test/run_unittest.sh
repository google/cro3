#!/bin/bash

# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Run all unittest in python/src/tools/test/*

# Set the starting work_dir to use later
work_dir=$(pwd)

# Exit if any command fails.
set -e

# Determine the full path to this script and use it to resolve the checkout src path.
readonly script_dir="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"
src="${script_dir}/../../../../../../../../../"
# Obtain the src_root without ../
cd $src
src_root=$(pwd)

# Swap back to the src path.
cd $work_dir

# Set the src/config/bin dir and load the common.sh src
readonly config_bin_dir="${src_root}/config/bin"
source "${config_bin_dir}/common.sh"

create_venv

python3.6 -m unittest