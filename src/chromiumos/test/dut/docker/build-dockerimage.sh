#!/bin/bash
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -eE -o functrace

# Print context information in the event of a failure to help debugging.
failure() {
  local lineno=$1
  local msg=$2
  echo "failed at ${lineno}: ${msg}" >&2
}
trap 'failure ${LINENO} "$BASH_COMMAND"' ERR

readonly script_dir="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"

source "${script_dir}/../../../../../test/docker/util.sh"

usage() {
    echo "Usage: $0 <chroot> <sysroot> [options] [key=value...]"
    echo
    echo "Build a docker container for the cros-dut service."
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

chroot="$1"; shift
shift # don't care about sysroot

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

build_server_image                             \
    --service "cros-dut"                       \
    --docker_file "${script_dir}/Dockerfile"   \
    --chroot "${chroot}"                       \
    --tags "${tags}"                           \
    --output "${output}"                       \
    --host "${host}"                           \
    --project "${project}"                     \
    "${@}"
