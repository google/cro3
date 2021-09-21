#!/usr/bin/env bash
#
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Runs testplan.go on an example SourceTestPlan, with config from
# config-internal.

set -e

usage="Run testplan.go on an example SourceTestPlan.

This script is just for seeing an example run of testplan.go an experimenting
with changes difficult to unit test (e.g. logging). It directly calls 'go run'
outside of Portage, so will fail if dependencies are not installed.

This script uses the BuildSummaryList and DutAttributesList checked into
config-internal.

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

script_dir="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"

cd "${script_dir}"

config_internal_dir="$(realpath -e ../../../../../../../config-internal)"
config_dir="$(realpath -e ../../../../../../../config)"

dut_attributes="${config_dir}/generated/dut_attributes.jsonproto"
build_metadata="${config_internal_dir}/build/generated/build_metadata.jsonproto"
flat_config_list="${config_internal_dir}/hw_design/generated/flattened.binaryproto"

if [[ ! -f ${dut_attributes} ]]; then
    echo "Expected to find DutAttributesList at ${dut_attributes}"
    exit 1
else
    echo "Using DutAttributeList at ${dut_attributes}"
fi

if [[ ! -f ${build_metadata} ]]; then
    echo "Expected to find BuildMetadataList at ${build_metadata}"
    exit 1
else
    echo "Using BuildMetadataList at ${build_metadata}"
fi


if [[ ! -f ${flat_config_list} ]]; then
    echo "Expected to find FlatConfigList at ${flat_config_list}"
    exit 1
else
    echo "Using FlatConfigList at ${flat_config_list}"
fi


outDir=$(mktemp -d)
out=${outDir}/coverage_rules.jsonproto
textSummaryOut=${outDir}/coverage_rules_summary.txt

echo "Running testplan.go, writing CoverageRules to ${out}"

set -x

go run testplan.go generate \
  -plan example_source_test_plan.textpb \
  -dutattributes "${dut_attributes}" \
  -buildmetadata "${build_metadata}" \
  -flatconfiglist "${flat_config_list}" \
  -out "${out}" \
  -textsummaryout "${textSummaryOut}" \
  "$@"
