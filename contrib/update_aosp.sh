#!/bin/bash
# Copyright 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Loads script libraries.
CONTRIB_DIR=$(dirname "$(readlink -f "$0")")
. "${CONTRIB_DIR}/common.sh" || exit 1

usage() {
  cat >&2 <<EOF
Use:
  update_aosp.sh [all] [<add_targets> ...] [~<remove_targets> ...]

Arguments:
  all: Include all the AOSP targets from chromeos-base/*
  <add_target>: Include the given package name in the uprev, such as
                "chromeos-base/libbrillo".
  ~<remove_target>: Filter out from the list of targets the given package name.
                    This is useful in combination with "all".

Example:
  ./update_aosp.sh all ~chromeos-base/webserver brillo-base/libsparse
EOF
}

# Script must run inside the chroot.
assert_inside_chroot

OVERLAY="${SRC_ROOT}/third_party/chromiumos-overlay"
cd "${OVERLAY}" || \
  die "Need to run inside the chroot."

REPOS=()

for arg in "$@"; do
  case "${arg}" in
    "all")
      for f in chromeos-base/*/*9999.ebuild; do
        if grep '^CROS_WORKON_BLACKLIST=1$' "$f" >/dev/null && \
           grep '^CROS_WORKON_REPO.*android.googlesource.com' "$f" >/dev/null; then
          REPOS+=($(dirname $f))
        fi
      done
    ;;
    "~"*)
      FILTERED=()
      for repo in "${REPOS[@]}"; do
        if [[ "~${repo}" != "${arg}" ]]; then
          FILTERED+=( "${repo}" )
        fi
      done
      REPOS=( "${FILTERED[@]}" )
    ;;
    ue)
      REPOS+=(
        "chromeos-base/update_engine"
        "chromeos-base/update_engine-client"
      )
    ;;
    "-"*)
      echo "Unknown option ${arg}" >&2
      usage
      exit 1
    ;;
    *)
      REPOS+=( "${arg}" )
  esac
done

if [[ "${#REPOS[@]}" == 0 ]]; then
  usage
  exit 1
fi

# Sort the repo to be more consistent.
REPOS=( $(echo "${REPOS[@]}" | tr ' ' '\n' | sort) )
echo "Will uprev the following ${#REPOS[@]} repos:"
for repo in "${REPOS[@]}"; do
  echo " * ${repo}"
done

### Do the actual work now ###
git diff-files || \
  die "There are uncommited changes in chromiumos-overlay"

repos_str=$(echo "${REPOS[@]}" | tr ' ' ':')
set -x

git checkout -f cros/master
git branch -D stabilizing_branch 2>/dev/null
cros_mark_as_stable commit -p "${repos_str}" --force --list-changes 100 || \
  die "cros_mark_as_stable failed"

git show --find-copies-harder HEAD

echo "New stabilizing_branch ready. Amend message and upload."
