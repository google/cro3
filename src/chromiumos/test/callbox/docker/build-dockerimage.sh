#!/bin/bash
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
readonly script_dir="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"

source "${script_dir}/../../../../../test/docker/util.sh"

usage() {
    echo "Usage: $0 <chroot> <sysroot> [options] [key=value...]"
    echo
    echo "Build a docker container for the cros-callbox service."
    echo
    echo "Args:"
    echo "  chroot  - Path to the ChromeOS chroot on the host system."
    echo "  sysroot - Path inside of the chroot to the board sysroot."
    echo "  labels  - Zero or more key=value strings to apply as labels to container."
    echo
    echo "Options:"
    echo "  --tags/-t - Comma separated list of tag names to apply to container"
    exit 1
}

if [[ $# -lt 2 ]]; then
    usage
fi

readonly chroot_path="$1"; shift
readonly sysroot_path="$1"; shift

host=""
project=""
tags=""
output=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --host|-h)
            host="$2"
            shift 2
            ;;
        --project|-p)
            project="$2"
            shift 2
            ;;
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


readonly output_dir="tmp/docker/croscallbox"
readonly full_output_dir="${chroot_path}/${sysroot_path}/${output_dir}"

prep_container

build_container_image                                \
    --service "cros-callbox"                         \
    --docker_file "${script_dir}/Dockerfile"         \
    --chroot "${chroot_path}"                        \
    --tags "${tags}"                                 \
    --output "${output}"                             \
    --host "${host}"                                 \
    --project "${project}"                           \
    "${@}"

