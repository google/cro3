#!/bin/bash

# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Gathers and stages all of the needed files for a "Docker Build ."

# Set the starting work_dir to use later
work_dir=$(pwd)

# Exit if any command fails.
set -e

# Determine the full path to this script and use it to resolve the checkout src path.
readonly script_dir="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"
src="${script_dir}/../../../../../"
# Obtain the src_root without ../
cd $src
src_root=$(pwd)

# Swap back to the src path.
cd $work_dir

# Set the src/config/bin dir and load the common.sh src
readonly config_bin_dir="${src_root}/config/bin"
source "${config_bin_dir}/common.sh"

create_venv

# $chroot_path $sysroot_path $output_path are set as ENV VAR's.
python3.6 container_prep.py -chroot=${chroot_path} -sysroot=${sysroot_path} -path=${output_path} -force_path=True -src=${src_root}
