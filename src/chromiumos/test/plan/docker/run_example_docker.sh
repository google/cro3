#!/usr/bin/env bash
#
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

usage="Run testplan.go on an example SourceTestPlan using Docker.

This demonstrates running the gcr.io/chromeos-bot/testplan Docker image. Bind
mounts are used for the input and output of the testplan tool.

Flags are passed through to testplan.go's generate command,
e.g. '-alsologtostderr'.

Usage: ${0} [options] <testplan.go generate flags>

Options:
  -h, --help       This help output."

while [[ $# -ne 0 ]]; do
  case $1 in
    -h|--help)
    exec printf '%b\n' "${usage}"
    ;;
  *)
    ARGS+=( "$1" )
    ;;
  esac
  shift
done
set -- "${ARGS[@]}" "$@"

set -x

script_dir="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"

cd "${script_dir}"

input_tmpdir=$(mktemp -d)
output_tmpdir=$(mktemp -d)
readonly input_tmpdir output_tmpdir

trap 'rm -rf ${input_tmpdir}' EXIT

config_internal_path=$(realpath ../../../../../../../config-internal)
config_path=$(realpath ../../../../../../../config)

readonly config_internal_path config_path

cp "${config_internal_path}/hw_design/generated/flattened.binaryproto" "${input_tmpdir}"
cp "${config_internal_path}/build/generated/build_metadata.jsonproto" "${input_tmpdir}"
cp "${config_path}/generated/dut_attributes.jsonproto" "${input_tmpdir}"
cp ../cmd/example_source_test_plan.textpb "${input_tmpdir}"

sudo docker run \
    --mount type=bind,source="${input_tmpdir}",target=/input,readonly \
    --mount type=bind,source="${output_tmpdir}",target=/output \
    "gcr.io/chromeos-bot/testplan:local-${USER}" generate \
    -plan /input/example_source_test_plan.textpb \
    -dutattributes /input/dut_attributes.jsonproto \
    -buildmetadata /input/build_metadata.jsonproto \
    -flatconfiglist /input/flattened.binaryproto \
    -out /output/coverage_rules.jsonproto \
    -textsummaryout /output/summary.txt \
    "$@"

echo "Output written to host at ${output_tmpdir}"
