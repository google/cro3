#!/bin/bash
#
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Shared library for searching and choosing CrOS images from a large collection
# of archived versions.
#
# This library deals with CrOS versions in four forms:
#
# version string: e.g. "R12-3456.7.8"
#   Completely specifies a CrOS version as release, major, minor and revision
#   numbers. The revision number may be followed by a '-' or '.' and arbitrary
#   characters, which will be ignored (e.g. "R12-3456.7.8-a9-b123").
#
# version pattern: e.g. "R12-3456", "3456.7", etc.
#   Specifies a partial CrOS version by omitting some of the numbers. For
#   example, all of the following patterns would match "R12-3456.7.8":
#     '', R12, R12-3456, R12-3456.7, R12-3456.7.8, 3456, 3456.7, 3456.7.8
#
# numeric version: e.g. "12 3456 7 8"
#   A version written as four space-separated integers corresponding to the
#   release, major, minor and revision numbers. The last integer may be
#   followed by another space and arbitrary characters, which will be ignored.
#
# numeric pattern: e.g. "12 3456 -1 -1"
#   A version pattern written as four space-separated integers corresponding to
#   the release, major, minor and revision numbers. Unrestricted fields are
#   indicated by negative values. The last integer may be followed by another
#   space and arbitrary characters, which will be ignored.

### GENERIC FUNCTIONS

# Usage: cros_archive_get_numeric_version version
# Generates a numeric version for the specified version string.
#
# Writes the numeric version to stdout and returns success. If the version
# string is malformed, will produce no output and return failure.
cros_archive_get_numeric_version() {
  local arg_{rel,ver,maj,min,rev,tail}

  # BUG(cwolfe):
  #     For some reason, attaching the next IFS to its read results in the IFS
  #     being ignored during cros_archive_filter_url_version_newest. This only
  #     occurs when run in the chroot (bash 4.2.20) and not on my workstation
  #     (bash 4.1.5). Hacking it to work for the moment, and need to figure out
  #     whether I've discovered a weird feature or a bash bug.
  #
  # Absent the bug, the next four lines should be:
  #   IFS='-' read -r arg_{rel,ver,tail} <<<"$1"
  local old_ifs="${IFS}"
  IFS='-'
  read -r arg_{rel,ver,tail} <<<"$1"
  IFS="${old_ifs}"

  IFS='.' read -r arg_{maj,min,rev,tail} <<<"${arg_ver}"
  arg_rel=${arg_rel#R}
  if [[ -z ${arg_rel} || -z ${arg_maj} ||
        -z ${arg_min} || -z ${arg_rev} ]]; then
    return 1  # Malformed version
  fi

  printf '%d %d %d %d\n' "${arg_rel}" "${arg_maj}" "${arg_min}" "${arg_rev}"
}

# Usage: cros_archive_get_numeric_pattern version
# Generates a numeric pattern corresponding to the specified version pattern.
#
# Writes the numeric pattern to stdout and returns success. If the version
# pattern is malformed or contains extra characters, will produce no output and
# return failure.
cros_archive_get_numeric_pattern() {
  local arg_{rel,ver,maj,min,rev,tail}

  IFS='-' read -r arg_{rel,ver,tail} <<<"$1"
  if [[ -n ${arg_tail} ]]; then
    return 1  # Malformed pattern: extra characters
  fi
  if [[ ${arg_rel:0:1} == 'R' ]]; then
    arg_rel=${arg_rel#R}  # Strip the 'R' prefix
  elif [[ -n ${arg_rel} ]]; then
    arg_ver=${arg_rel}  # Actually got a version with no release.
    arg_rel=
  fi
  if [[ -n ${arg_ver} ]]; then
    IFS='.' read -r arg_{maj,min,rev,tail} <<<"${arg_ver}"
    if [[ -n ${arg_tail} ]]; then
      return 1  # Malformed pattern: extra characters
    fi
  fi

  printf '%d %d %d %d\n' \
         "${arg_rel:--1}" "${arg_maj:--1}" "${arg_min:--1}" "${arg_rev:--1}"
}

# Usage: cros_archive_get_wildcard_pattern version
# Generates a wildcard pattern that will match the specified numeric version.
#
# Writes the wildcard pattern to stdout and returns success. If the numeric
# version is malformed, will produce no output and return failure.
cros_archive_get_wildcard_pattern() {
  local arg_{rel,maj,min,rev}
  read -r arg_{rel,maj,min,rev} <<<"$1"

  # Replace any negative fields with '*'.
  [[ ${arg_rel} -ge 0 ]] || arg_rel='*'
  [[ ${arg_maj} -ge 0 ]] || arg_maj='*'
  [[ ${arg_min} -ge 0 ]] || arg_min='*'
  [[ ${arg_rev} -ge 0 ]] || arg_rev='*'

  printf "R%s-%s.%s.%s\n" "${arg_rel}" "${arg_maj}" "${arg_min}" "${arg_rev}"
}

# Usage: cros_archive_test_numeric_version_matches pattern version
# Tests whether a numeric pattern matches a numeric version.
#
# Returns success if the pattern matches the version and failure otherwise.
cros_archive_test_numeric_version_matches() {
  local -a pattern version
  read -ra pattern <<<"$1"
  read -ra version <<<"$2"
  if [[ ${#pattern[@]} -lt 4 || ${#version[@]} -lt 4 ]]; then
    return 1  # Malformed pattern or version
  fi

  local i
  for i in {0..3}; do
    if [[ ${pattern[$i]} -ge 0 && ${pattern[$i]} -ne ${version[$i]} ]]; then
      return 1  # Version does not match pattern
    fi
  done
  return 0  # Version matches pattern
}

# Usage: cros_archive_test_numeric_version_newer first second
# Tests whether the first numeric version is newer than the second.
#
# Returns success if the first numeric version is newer than the second,
# and failure otherwise.
cros_archive_test_numeric_version_newer() {
  local -a first second
  read -ra first <<<"$1"
  read -ra second <<<"$2"
  if [[ ${#first[@]} -lt 4 || ${#second[@]} -lt 4 ]]; then
    return 1  # Malformed version
  fi

  local i
  for i in {0..3}; do
    if [[ ${first[$i]} -ne ${second[$i]} ]]; then
      if [[ ${first[$i]} -gt ${second[$i]} ]]; then
        return 0  # First is indeed newer then second.
      else
        return 1  # First is older than second.
      fi
    fi
  done
  return 1  # First and second are equal.
}

# Usage: cros_archive_filter_numeric_version_matches pattern
# Filters a stream of numeric versions, keeping those which match the specified
# numeric pattern.
#
# Reads lines from stdin. Each line must be a numeric version. If a line
# matches the pattern it will be written to stdout in its entirety, otherwise
# the line will be discarded.
#
# Returns success at the end if input.
cros_archive_filter_numeric_version_matches() {
  local pattern="$1"
  local version
  while read -r version; do
    if cros_archive_test_numeric_version_matches "${pattern}" "${version}"; then
      printf '%s\n' "${version}"
    fi
  done
}

# Usage: cros_archive_filter_numeric_version_newest
# Filters a stream of numeric versions to choose the newest.
#
# Reads lines from stdin. Each line must be a numeric version. Once the end of
# input has been reached, the line containing the newest numeric version will
# be written to stdout in its entirety. Will not produce any output if no
# versions have been read.
#
# Returns success unless an error was encountered, even if no versions were
# processed.
cros_archive_filter_numeric_version_newest() {
  local best
  local curr
  while read -r curr; do
    if [[ -z ${best} ]] ||
       cros_archive_test_numeric_version_newer "${curr}" "${best}"; then
      best="${curr}"
    fi
  done
  if [[ -n ${best} ]]; then
    printf '%s\n' "${best}"
  fi
}

# Usage: cros_archive_filter_url_version_newest regexp [pattern]
# Filters a stream of URLs to choose the one containing the newest version
# string. Optionally discards versions which do not match the specified numeric
# pattern.
#
# The regexp must contain a single parenthesized subexpression that selects the
# version string from a URL. Any URL which does not match this regexp or does
# not record a parenthesized subexpression will be discarded.
#
# Reads lines from stdin, each of which must consist of a single URL. Once the
# end of input has been reached, the URL containing the newest version string
# will be written to stdout.
#
# Returns success unless an error was encountered, even if no URLs were found.
cros_archive_filter_url_version_newest() {
  local regexp="$1"
  local pattern="${2:--1 -1 -1 -1}"

  get_numeric_result() {
    local input
    while read -r input; do
      if [[ ! ( ${input} =~ ^${regexp}$ ) || ${#BASH_REMATCH[@]} -lt 1 ]]; then
        continue
      fi
      local version=$(cros_archive_get_numeric_version "${BASH_REMATCH[1]}")
      printf '%s %s\n' "${version}" "${input}"
    done |
    cros_archive_filter_numeric_version_matches "${pattern}" |
    cros_archive_filter_numeric_version_newest
  }

  local -a result
  if ! read -a result < <(get_numeric_result); then
    return 0  # No URL available
  fi

  # Drop the first four elements in the result array, as they contain the
  # numeric version.
  printf '%s\n' "${result[*]:4}"
}

### GOOGLE STORAGE SPECIFIC FUNCTIONS
#
# This code addresses the problem of getting images from a GS archive in two
# stages: it generates a set of wildcards passed to "gsutil ls", and then uses
# a regexp to parse the version numbers out of the list. These two steps are
# necessary because gsutil supports only simple glob-style wildcards and can
# not do version-number ordering of the results. Fortunately the processing
# can be run in parallel to the "gsutil ls", so the overhead is small.
#

# Usage: cros_archive_gs_get_url_wildcards channel board [pattern]
# Gets one or more URL wildcard for a specified channel and board which will
# include at least the archives corresponding to the specified numeric pattern.
#
# The 'archive' virtual channel is loaded from gs://chromeos-image-archive.
# All other channels will be requested from gs://chromeos-releases.
cros_archive_gs_get_url_wildcards() {
  local channel="$1"
  local board="$2"
  local pattern=$(cros_archive_get_wildcard_pattern "${3:--1 -1 -1 -1}")

  # Add a '*' after the pattern, as some of the uploaded paths (but not all)
  # contain additional numbers for attempt and build like "-a0-b1234". To
  # avoid doubling '*'s, also remove any trailing '*' from the pattern.
  pattern="${pattern%\*}*"

  if [[ ${channel} == 'archive' ]]; then
    # Most boards use a -release builder, so output that URL first.
    local suffix
    for suffix in release full; do
      printf 'gs://chromeos-image-archive/%s-%s/%s/image.zip\n' \
             "${board}" "${suffix}" "${pattern}"
    done
  else
    printf 'gs://chromeos-releases/%s/%s/%s/ChromeOS-%s-%s.zip\n' \
           "${channel}-channel" "${board}" "${pattern#R*-}" "${pattern}" \
           "${board}"
  fi
}

# Usage: cros_archive_gs_get_url_regexp channel board
# Gets a regexp which can be used to extract the version from URLs associated
# with the specified channel and board.
#
# The 'archive' virtual channel is loaded from gs://chromeos-image-archive.
# All other channels will be requested from gs://chromeos-releases.
cros_archive_gs_get_url_regexp() {
  local channel="$1"
  local board="$2"
  local pattern=$(cros_archive_get_wildcard_pattern "${3:--1 -1 -1 -1}")

  # The version_regexp picks out and records two dash-separated components that
  # look like a CrOS version. In some cases it will be followed by another dash
  # and additional information, so we need to be a little careful about what it
  # matches.
  local version_regexp='(R[^/-]*-[^/-]*)'
  if [[ ${channel} == 'archive' ]]; then
    printf 'gs://chromeos-image-archive/%s[^/]*/%s[^/]*/image.zip\n' \
           "${board}" "${version_regexp}"
  else
    printf 'gs://chromeos-releases/%s/%s/[^/]*/ChromeOS-%s[^/]*-%s.zip\n' \
           "${channel}-channel" "${board}" "${version_regexp}" "${board}"
  fi
}

# Usage: cros_archive_gsutil_ls_filter
# Gets multiple directory listings from gsutil ls.
#
# Reads lines from stdin. Each line must be a gs:// URL, possibly containing
# wildcards. Will write zero or more lines to stdout containing the URLs which
# were returned from the server.
#
# Errors from gsutil related to there being no matching URLs will be ignored.
# Returns success unless an error was encountered, even if no URLs were found.
#
# Environment:
#   GSUTIL: name of gsutil program (default is 'gsutil')
cros_archive_gsutil_ls_filter() {
  local url
  while read -r url; do
    # Run gsutil with its stdout passed through and its stderr recorded.
    local rc=0
    exec 3>&1
    local error=$( ${GSUTIL:-gsutil} ls "${url}" 2>&1 1>&3 3>&- ) || rc=$?
    exec 3>&-

    # Ignore errors that only indicate no matches were found. This behavior
    # may vary between different versions of gsutil, so we should not assume
    # an empty result sets non-zero rc.
    if [[ ${rc} -ne 0 && ${error} != 'No matches for'* ]]; then
      printf 'gsutil: %s\n' "${error}" >&2
      return 1
    fi
  done
}

# Usage: cros_archive_gs_list channel board [pattern]
# Gets the list of URLs matching the specified channel and board which will
# satisfy the specified numeric pattern.
#
# This command calls the Google Storage backend to get a list of available
# files.
#
# Returns success unless an error was encountered, even if no URLs were found.
cros_archive_gs_list() {
  local channel="$1"
  local board="$2"
  local pattern=$(cros_archive_get_numeric_pattern "$3")

  local regexp=$(cros_archive_gs_get_url_regexp "${channel}" "${board}")

  cros_archive_gs_get_url_wildcards "${channel}" "${board}" "${pattern}" |
  cros_archive_gsutil_ls_filter |
  cros_archive_filter_url_version_newest "${regexp}" "${pattern}"
}

# Usage: cros_archive_gs_get_url_version channel board url
# Gets the version string contained in the image URL for a particular channel
# and board.
#
# Writes the version string to stdout and returns success. If the URL does not
# match the pattern expected for the channel and board will produce no output
# and return failure.
cros_archive_gs_get_url_version() {
  local channel="$1"
  local board="$2"
  local url="$3"

  local regexp=$(cros_archive_gs_get_url_regexp "${channel}" "${board}")

  if [[ ! ( ${url} =~ ^${regexp}$ ) || ${#BASH_REMATCH[@]} -lt 1 ]]; then
    return 1
  fi
  echo "${BASH_REMATCH[1]}"
}
