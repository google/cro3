#!/bin/bash
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -eE -o functrace

# Print context information in the event of a failure to help debugging.
failure() {
  local lineno=$1
  local msg=$2
  echo "failed at $lineno: $msg" >&2
}
trap 'failure ${LINENO} "$BASH_COMMAND"' ERR

script_dir="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"
readonly script_dir

usage() {
    echo "Usage: $0 <chroot> <sysroot> [options] [key=value...]"
    echo
    echo "Build a docker container for the cros-test service."
    echo
    echo "Args:"
    echo "  chroot  - Path to the ChromeOS chroot on the host system."
    echo "  sysroot - Path inside of the chroot to the board sysroot."
    echo "  labels  - Zero or more key=value strings to apply as labels to container."
    echo
    echo "Options:"
    echo "  --tags/-t - Comma separated list of tag names to apply to container"
    echo "  --output/-o - File to which to write ContainerImageInfo jsonproto"
    exit 1
}

if [[ $# -lt 3 ]]; then
    usage
fi

prep_container() {
  # Determine the full path to this script and use it to resolve the checkout src path.
  readonly src="${script_dir}/../../../../../"

  src_root="$(realpath "${src}")"

  # Set the src/config/bin dir and load the common.sh src
  readonly config_bin_dir="${src_root}/config/bin"
  # shellcheck source=/dev/null
  source "${config_bin_dir}/common.sh"

  create_venv

  python3 "${script_dir}"/container_prep.py -chroot="${chroot_path}" -sysroot="${sysroot_path}" -path="${output_dir}" -force_path=True -src="${src_root}"
}


readonly chroot_path="$1"; shift
readonly sysroot_path="$1"; shift

tags=""
output=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --tags|-t)
            tags="$2"
            shift 2
            ;;
        --output|-o)
            output="$2"
            shift 2
            ;;
        *)
            break
            ;;
    esac
done


readonly output_dir="tmp/docker/crostest"
readonly full_output_dir="${chroot_path}/${sysroot_path}/${output_dir}"

prep_container

# shellcheck source=/dev/null
source "${script_dir}/../../../test/docker/util.sh"

build_container_image               \
    "cros-test"             \
    "${full_output_dir}/Dockerfile" \
    "${chroot_path}"                \
    "${tags}"                       \
    "${output}"                     \
    "$@"
