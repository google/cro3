#!/bin/bash
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e
script_dir="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"
readonly script_dir

source "${script_dir}/../../../../../test/docker/util.sh"

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

build_server_image                               \
    --service "testplan"                         \
    --docker_file "${script_dir}/Dockerfile"     \
    --tags "${tags}"                             \
    --output "${output}"                         \
    --host "${host}"                             \
    --project "${project}"                       \
    "${@}"
