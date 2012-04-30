#!/bin/bash
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#

set -o errexit
set -o pipefail

. "$(dirname "$(readlink -f "$0")")"/cros_archive.sh

### TESTING FUNCTIONS

total_passed=0
total_failed=0

expect() {
  local caller_line="${BASH_SOURCE[1]}:${BASH_LINENO[0]}"
  local output='*'
  local status='0'
  unset OPTIND
  while getopts ':o:s:' OPTOPT; do
    case ${OPTOPT} in
      'o') output=${OPTARG} ;;
      's') status=${OPTARG} ;;
      '?') echo "expect: error processing option ${OPTARG}" \
                "(called from ${caller_line})"
           exit 2
      ;;
    esac
  done
  shift $(( OPTIND - 1 ))
  local cmd=( "$@" )

  local actual_output
  local actual_status=0
  actual_output=$( "${cmd[@]}" ) || actual_status=$?

  local wrong_status
  local wrong_output
  if [[ ${status} != '*' && ${actual_status} -ne ${status} ]]; then
    wrong_status='yes'
  fi
  if [[ ${output} != '*' && ${actual_output} != "${output}" ]]; then
    wrong_output='yes'
  fi

  if [[ -n ${wrong_status} || -n ${wrong_output} ]]; then
    echo "FAIL at ${caller_line}: ${cmd[@]}"
    if [[ -n ${wrong_status} ]]; then
      echo "  exit status was ${actual_status}, expected ${status}"
    fi
    if [[ -n ${wrong_output} ]]; then
      echo "  the command produced unexpected content on stdout"
      echo "  expected: '${output}'"
      echo "  received: '${actual_output}'"
    fi
    echo
    : $(( ++total_failed ))
  else
    : $(( ++total_passed ))
  fi
}

### TESTS

### cros_archive_get_numeric_version

expect -o '12 3456 7 8' \
    cros_archive_get_numeric_version 'R12-3456.7.8'

expect -o '12 3456 7 8' \
    cros_archive_get_numeric_version 'R12-3456.7.8-a9-b123'

### cros_archive_get_numeric_pattern

expect -o '-1 -1 -1 -1' \
    cros_archive_get_numeric_pattern ''

expect -o '12 -1 -1 -1' \
    cros_archive_get_numeric_pattern 'R12'

expect -o '12 3456 -1 -1' \
    cros_archive_get_numeric_pattern 'R12-3456'

expect -o '12 3456 7 -1' \
    cros_archive_get_numeric_pattern 'R12-3456.7'

expect -o '12 3456 7 8' \
    cros_archive_get_numeric_pattern 'R12-3456.7.8'

expect -o '-1 3456 -1 -1' \
    cros_archive_get_numeric_pattern '3456'

expect -o '-1 3456 7 -1' \
    cros_archive_get_numeric_pattern '3456.7'

expect -o '-1 3456 7 8' \
    cros_archive_get_numeric_pattern '3456.7.8'

### cros_archive_get_wildcard_pattern

expect -o 'R*-*.*.*' \
    cros_archive_get_wildcard_pattern '-1 -1 -1 -1'

expect -o 'R12-*.*.*' \
    cros_archive_get_wildcard_pattern '12 -1 -1 -1'

expect -o 'R12-3456.*.*' \
    cros_archive_get_wildcard_pattern '12 3456 -1 -1'

expect -o 'R12-3456.7.*' \
    cros_archive_get_wildcard_pattern '12 3456 7 -1'

expect -o 'R12-3456.7.8' \
    cros_archive_get_wildcard_pattern '12 3456 7 8'

expect -o 'R*-3456.*.*' \
    cros_archive_get_wildcard_pattern '-1 3456 -1 -1'

expect -o 'R*-3456.7.*' \
    cros_archive_get_wildcard_pattern '-1 3456 7 -1'

expect -o 'R*-3456.7.8' \
    cros_archive_get_wildcard_pattern '-1 3456 7 8'

### cros_archive_test_numeric_version_matches

expect cros_archive_test_numeric_version_matches \
    '-1 -1 -1 -1' '12 3456 7 8'

expect cros_archive_test_numeric_version_matches \
    '12 -1 -1 -1' '12 3456 7 8'

expect cros_archive_test_numeric_version_matches \
    '12 3456 -1 -1' '12 3456 7 8'

expect cros_archive_test_numeric_version_matches \
    '12 3456 7 -1' '12 3456 7 8'

expect cros_archive_test_numeric_version_matches \
    '12 3456 7 8' '12 3456 7 8'

expect cros_archive_test_numeric_version_matches \
    '-1 3456 -1 -1' '12 3456 7 8'

expect cros_archive_test_numeric_version_matches \
    '-1 3456 7 -1' '12 3456 7 8'

expect cros_archive_test_numeric_version_matches \
    '-1 3456 7 8' '12 3456 7 8'

expect -s 1 cros_archive_test_numeric_version_matches \
    '12 -1 -1 -1' '99 3456 7 8'

expect -s 1 cros_archive_test_numeric_version_matches \
    '12 3456 -1 -1' '12 9999 7 8'

expect -s 1 cros_archive_test_numeric_version_matches \
    '12 3456 7 -1' '12 3456 9 8'

expect -s 1 cros_archive_test_numeric_version_matches \
    '12 3456 7 8' '12 3456 7 9'

expect -s 1 cros_archive_test_numeric_version_matches \
    '-1 3456 -1 -1' '12 9999 7 8'

expect -s 1 cros_archive_test_numeric_version_matches \
    '-1 3456 7 -1' '12 3456 9 8'

expect -s 1 cros_archive_test_numeric_version_matches \
    '-1 3456 7 8' '12 3456 7 9'

### cros_archive_test_numeric_version_newer

expect cros_archive_test_numeric_version_newer \
    '12 3456 7 8' '11 3456 7 8'

expect cros_archive_test_numeric_version_newer \
    '12 3456 7 8' '12 3455 7 8'

expect cros_archive_test_numeric_version_newer \
    '12 3456 7 8' '12 3456 6 8'

expect cros_archive_test_numeric_version_newer \
    '12 3456 7 8' '12 3456 7 7'

expect -s 1 cros_archive_test_numeric_version_newer \
    '12 3456 7 8' '12 3456 7 8'

expect -s 1 cros_archive_test_numeric_version_newer \
    '12 3456 7 8' '13 1 1 1'

expect -s 1 cros_archive_test_numeric_version_newer \
    '12 3456 7 8' '12 3457 1 1'

expect -s 1 cros_archive_test_numeric_version_newer \
    '12 3456 7 8' '12 3456 8 1'

expect -s 1 cros_archive_test_numeric_version_newer \
    '12 3456 7 8' '12 3456 7 9'

### cros_archive_filter_numeric_version_matches

numeric_version_list="\
12 3456 7 8
11 3456 7 8
13 3456 7 8
12 3455 7 8
12 3457 7 8
12 3456 6 8
12 3456 8 8
12 3456 7 7
12 3456 7 9
"

expect -o $'12 3456 7 8' \
    cros_archive_filter_numeric_version_matches '12 3456 7 8' \
    <<<"${numeric_version_list}"

expect -o $'12 3456 7 8\n11 3456 7 8\n13 3456 7 8' \
    cros_archive_filter_numeric_version_matches '-1 3456 7 8' \
    <<<"${numeric_version_list}"

expect -o $'12 3456 7 8\n12 3455 7 8\n12 3457 7 8' \
    cros_archive_filter_numeric_version_matches '12 -1 7 8' \
    <<<"${numeric_version_list}"

expect -o $'12 3456 7 8\n12 3456 6 8\n12 3456 8 8' \
    cros_archive_filter_numeric_version_matches '12 3456 -1 8' \
    <<<"${numeric_version_list}"

expect -o $'12 3456 7 8\n12 3456 7 7\n12 3456 7 9' \
    cros_archive_filter_numeric_version_matches '12 3456 7 -1' \
    <<<"${numeric_version_list}"

### cros_archive_filter_numeric_version_newest

expect -o '13 3456 7 8' \
    cros_archive_filter_numeric_version_newest \
    <<<"${numeric_version_list}"

numeric_version_list="\
1 1 1 1
1 1 1 0
1 1 0 0
1 0 0 0
0 0 0 0
"

expect -o '1 1 1 1' \
    cros_archive_filter_numeric_version_newest \
    <<<"${numeric_version_list}"

### cros_archive_filter_url_version_newest

url_regexp='http://example.net/(.*)/image.zip'

expect -o '' \
    cros_archive_filter_url_version_newest "${url_regexp}" \
    <<<""

url_list="\
http://example.net/R12-3456.7.8/image.zip
http://example.net/R11-3456.7.8/image.zip
http://example.net/R13-3456.7.8/image.zip
http://example.net/R12-3455.7.8/image.zip
http://example.net/R12-3457.7.8/image.zip
http://example.net/R12-3456.6.8/image.zip
http://example.net/R12-3456.8.8/image.zip
http://example.net/R12-3456.7.7/image.zip
http://example.net/R12-3456.7.9/image.zip"

expect -o "\
http://example.net/R13-3456.7.8/image.zip" \
    cros_archive_filter_url_version_newest "${url_regexp}" \
    <<<"${url_list}"

url_list="\
http://example.net/R1-1.1.1/image.zip
http://example.net/R1-1.1.0/image.zip
http://example.net/R1-1.0.0/image.zip
http://example.net/R1-0.0.0/image.zip
http://example.net/R0-0.0.0/image.zip"

expect -o 'http://example.net/R1-1.1.1/image.zip' \
    cros_archive_filter_url_version_newest "${url_regexp}" \
    <<<"${url_list}"

### cros_archive_gs_get_url_wildcards

expect -o "\
gs://chromeos-image-archive/x86-generic-release/R*-*.*.*/image.zip
gs://chromeos-image-archive/x86-generic-full/R*-*.*.*/image.zip" \
    cros_archive_gs_get_url_wildcards 'archive' 'x86-generic'

expect_base='gs://chromeos-releases/canary-channel/x86-alex'
expect -o "${expect_base}/*.*.*/ChromeOS-R*-*.*.*-x86-alex.zip" \
    cros_archive_gs_get_url_wildcards 'canary' 'x86-alex'

### cros_archive_gs_get_url_regexp

url_list="\
gs://chromeos-image-archive/x86-generic-full/R18-1660.0.0-a1-b1626/image.zip
gs://chromeos-image-archive/x86-generic-full/R20-2223.0.0-a1-b3069/image.zip"
regexp=$(cros_archive_gs_get_url_regexp 'archive' 'x86-generic')
expect -o "${url_list}" grep -E "${regexp}" <<<"${url_list}"

expect_base='gs://chromeos-releases/canary-channel'
url_list="\
${expect_base}/x86-alex/1590.2.0/ChromeOS-R18-1590.2.0-a1-b18-x86-alex.zip
${expect_base}/x86-alex/2223.0.0/ChromeOS-R20-2223.0.0-x86-alex.zip"
regexp=$(cros_archive_gs_get_url_regexp 'canary' 'x86-alex')
expect -o "${url_list}" grep -E "${regexp}" <<<"${url_list}"

### cros_archive_gs_list

archive_base='gs://chromeos-image-archive/x86-generic-full'
canary_base='gs://chromeos-releases/canary-channel/x86-alex'
url_list="\
${archive_base}/R18-1659.0.0-a1-b1625/image.zip
${archive_base}/R18-1660.0.0-a1-b1626/image.zip
${archive_base}/R20-2223.0.0-a1-b3069/image.zip
${canary_base}/1589.0.0/ChromeOS-R18-1589.0.0-a1-b17-x86-alex.zip
${canary_base}/1590.2.0/ChromeOS-R18-1590.2.0-a1-b18-x86-alex.zip
${canary_base}/2223.0.0/ChromeOS-R20-2223.0.0-x86-alex.zip"

mock_gsutil() {
  if [[ $# -ne 2 || $1 != 'ls' ]]; then
    echo 'Mock expected usage to be "ls URL"' >&2
    return 1
  fi
  local pattern="$2"
  local found
  local url
  while read -r url; do
    if [[ ${url} == ${pattern} ]]; then
      echo ${url}
      found='yes'
    fi
  done <<<"${url_list}"
  if [[ -z ${found} ]]; then
    echo "No matches for ${pattern}" >&2
    return 1
  fi
}

GSUTIL=mock_gsutil
expect -o '' \
    cros_archive_gs_list archive x86-generic R17
expect -o "${archive_base}/R18-1660.0.0-a1-b1626/image.zip" \
    cros_archive_gs_list archive x86-generic R18
expect -o "${archive_base}/R20-2223.0.0-a1-b3069/image.zip" \
    cros_archive_gs_list archive x86-generic
expect -o '' \
    cros_archive_gs_list canary x86-alex R17
expect -o "${canary_base}/1590.2.0/ChromeOS-R18-1590.2.0-a1-b18-x86-alex.zip" \
    cros_archive_gs_list canary x86-alex R18
expect -o "${canary_base}/2223.0.0/ChromeOS-R20-2223.0.0-x86-alex.zip" \
    cros_archive_gs_list canary x86-alex

expect -o 'R18-1660.0.0' \
    cros_archive_gs_get_url_version archive x86-generic \
    "${archive_base}/R18-1660.0.0-a1-b1626/image.zip"
expect -o 'R20-2223.0.0' \
    cros_archive_gs_get_url_version archive x86-generic \
    "${archive_base}/R20-2223.0.0-a1-b3069/image.zip"

expect -o 'R18-1590.2.0' \
    cros_archive_gs_get_url_version canary x86-alex \
    "${canary_base}/1590.2.0/ChromeOS-R18-1590.2.0-a1-b18-x86-alex.zip"
expect -o 'R20-2223.0.0' \
    cros_archive_gs_get_url_version canary x86-alex \
    "${canary_base}/2223.0.0/ChromeOS-R20-2223.0.0-x86-alex.zip"

if [[ ${total_failed} -gt 0 ]]; then
  exit 1
fi
