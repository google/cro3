#!/bin/bash
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

die() { echo "$*" 1>&2 ; exit 1; }
[[ $# -ne 2 ]] && die "Need exactly 2 args: chroot_path and sysroot_path"

prep_container() {
  # Determine the full path to this script and use it to resolve the checkout src path.
  readonly src="${script_dir}/../../../../../"

  src_root="$(realpath "${src}")"

  # Set the src/config/bin dir and load the common.sh src
  readonly config_bin_dir="${src_root}/config/bin"
  # shellcheck source=/dev/null
  source "${config_bin_dir}/common.sh"

  create_venv

  python3 container_prep.py -chroot="${chroot_path}" -sysroot="${sysroot_path}" -path="${output_dir}" -force_path=True -src="${src_root}"
}


readonly script_dir="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"

readonly chroot_path="$1"
readonly sysroot_path="$2"
readonly output_dir="tmp/docker/testexeccontainer"
readonly full_output_dir="${chroot_path}/${sysroot_path}/${output_dir}"

prep_container

# shellcheck source=/dev/null
source "${script_dir}/../../../test/docker/util.sh"

build_container_image "testexeccontainer" "${full_output_dir}/Dockerfile" "${chroot_path}" "${sysroot_path}"
