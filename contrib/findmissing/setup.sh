#!/bin/bash
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Note: Collabora repository with pending patches
# https://git.collabora.com/cgit/linux.git/log/?h=topic/chromeos/waiting-for-upstream

stable_path=$(python -c "from config import STABLE_PATH; print(STABLE_PATH);")
stable_repo=$(python -c  "from config import STABLE_REPO; print(STABLE_REPO);")

chromeos_path=$(python -c "from config import CHROMEOS_PATH; print(CHROMEOS_PATH);")
chromeos_repo=$(python -c  "from config import CHROMEOS_REPO; print(CHROMEOS_REPO);")

upstream_path=$(python -c "from config import UPSTREAM_PATH; print(UPSTREAM_PATH);")
if [[ "$(dirname "${upstream_path}")" = "." ]]; then
  # Needs to be an absolute path name
  upstream_path="$(pwd)/${upstream_path}"
fi
upstream_repo=$(python -c  "from config import UPSTREAM_REPO; print(UPSTREAM_REPO);")

sbranches=("$(python -c "from config import STABLE_BRANCHES; print(STABLE_BRANCHES)" | tr -d "(),'")")
spattern=("$(python -c "from config import STABLE_PATTERN; print(STABLE_PATTERN)" | tr -d "(),'")")
cbranches=("$(python -c "from config import CHROMEOS_BRANCHES; print(CHROMEOS_BRANCHES)" | tr -d "(),'")")
cpattern=("$(python -c "from config import CHROMEOS_PATTERN; print(CHROMEOS_PATTERN)" | tr -d "(),'")")

# Simple clone:
# Clone repository, do not add 'upstream' remote
clone_simple()
{
  local destdir=$1
  local repository=$2
  local force=$3

  echo "Cloning ${repository} into ${destdir}"

  if [[ -d "${destdir}" ]]; then
    pushd "${destdir}" >/dev/null || exit
    git checkout master
    if [[ -n "${force}" ]]; then
      # This is needed if the origin may have been rebased
      git fetch origin
      git reset --hard origin/master
    else
      git pull
    fi
    popd >/dev/null || exit
  else
    git clone "${repository}" "${destdir}"
  fi
}

clone_simple "${upstream_path}" "${upstream_repo}"

# Complex clone:
# Clone repository, add 'upstream' remote,
# check out and update list of branches
clone_complex()
{
  local destdir=$1
  local repository=$2
  local pattern=$3
  local branches=("${!4}")

  echo "Cloning ${repository} into ${destdir}"

  if [[ -d "${destdir}" ]]; then
    pushd "${destdir}" >/dev/null || exit
    git reset --hard HEAD
    git fetch origin
    for branch in ${branches[*]}; do
      branch="$(printf '%s %s' "${pattern}" "${branch}")"
      if git rev-parse --verify "${branch}" >/dev/null 2>&1; then
        git checkout "${branch}"
        if ! git pull; then
          # git pull may fail if the remote repository was rebased.
          # Pull it the hard way.
          git reset --hard "origin/${branch}"
        fi
      else
        git checkout -b "${branch}" "origin/${branch}"
      fi
    done
    git remote -v | grep upstream || {
      git remote add upstream "${upstream_path}"
    }
    git fetch upstream
    popd >/dev/null || exit
  else
    git clone "${repository}" "${destdir}"
    pushd "${destdir}" >/dev/null || exit
    for branch in ${branches[*]}; do
      branch="$(printf '%s %s' "${pattern}" "${branch}")"
      git checkout -b "${branch}" "origin/${branch}"
    done
    git remote add upstream "${upstream_path}"
    git fetch upstream
    popd >/dev/null || exit
  fi
}

clone_complex "${stable_path}" "${stable_repo}" "${spattern[0]}" "${sbranches[*]}"
clone_complex "${chromeos_path}" "${chromeos_repo}" "${cpattern[0]}" "${cbranches[*]}"

echo "Initializing databases"
python initdb_upstream.py
python initdb_stable.py
python initdb_chromeos.py
