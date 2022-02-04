#!/bin/bash
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
readonly script_dir="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"

source "${script_dir}/../../../../../test/docker/util.sh"

usage() {
    echo "Usage: $0 [options] [key=value...]"
    echo
    echo "Build a docker container for the cros-callbox service."
    echo
    echo "Options:"
    echo "  --tags/-t - Comma separated list of tag names to apply to container"
    exit 1
}

chroot=""
host=""
project=""
tags=""
output=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --chroot|-c)
                chroot="$2"
                shift 2
                ;;
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


build_dir="/tmp/docker/cros-callbox"
mkdir -p "$build_dir"
cp -R "$script_dir" "$build_dir"

build_container_image                                \
    --service "cros-callbox"                         \
    --docker_file "${build_dir}/docker/Dockerfile"   \
    --chroot "${chroot}"                             \
    --tags "${tags}"                                 \
    --output "${output}"                             \
    --host "${host}"                                 \
    --project "${project}"                           \
    "${@}"

