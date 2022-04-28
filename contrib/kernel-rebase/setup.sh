#!/bin/bash
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Note: Collabora repository with pending patches
# https://git.collabora.com/cgit/linux.git/log/?h=topic/chromeos/waiting-for-upstream

chromeos_path=$(python3 -c "from common import chromeos_path; print(chromeos_path)")
chromeos_repo=$(python3 -c  "from config import chromeos_repo; print(chromeos_repo)")

stable_path=$(python3 -c "from common import stable_path; print(stable_path)")
stable_repo=$(python3 -c  "from config import stable_repo; print(stable_repo)")

upstream_path=$(python3 -c "from common import upstream_path; print(upstream_path)")
upstream_repo=$(python3 -c  "from config import upstream_repo; print(upstream_repo)")

next_path=$(python3 -c "from common import next_path; print(next_path)")
next_repo=$(python3 -c  "from config import next_repo; print(next_repo)")

rebase_baseline_branch=$(python3 -c "from config import rebase_baseline_branch; print(rebase_baseline_branch)")

android_repo=$(python3 -c  "from config import android_repo; print(android_repo)")
if [[ "${android_repo}" != "None" ]]; then
    android_baseline_branch=$(python3 -c "from config import android_baseline_branch; print(android_baseline_branch)")
    android_path=$(python3 -c "from common import android_path; print(android_path)")
fi

nextdb=$(python3 -c "from common import nextdb; print(nextdb)")
rebasedb=$(python3 -c "from common import rebasedb; print(rebasedb)")

progdir=$(dirname "$0")
cd "${progdir}" || exit 1

# Simple clone:
# Clone repository, do not add 'upstream' remote
clone_simple()
{
    local destdir=$1
    local repository=$2
    local force=$3

    echo "Cloning ${repository} into ${destdir}"

    if [[ -d "${destdir}" ]]; then
        pushd "${destdir}" >/dev/null || return 1
        git checkout master
        if [[ -n "${force}" ]]; then
            # This is needed if the origin may have been rebased
            git fetch -p origin
            git reset --hard origin/master
        else
            git pull -p
        fi
        popd >/dev/null || return 1
    else
        git clone "${repository}" "${destdir}"
    fi
}

clone_simple "${upstream_path}" "${upstream_repo}"

if [[ "${stable_repo}" != "None" ]]; then
    clone_simple "${stable_path}" "${stable_repo}"
fi

# Complex clone:
# Clone repository, check out branch, add 'upstream' remote
# Also, optionally, add 'next' remote
clone_complex()
{
    local destdir=$1
    local repository=$2
    local branch=$3

    echo "Cloning ${repository}:${branch} into ${destdir}"

    if [[ -d "${destdir}" ]]; then
        pushd "${destdir}" >/dev/null || return 1
        git reset --hard HEAD
        git fetch origin
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
        git remote -v | grep upstream || {
            git remote add upstream "../$(basename "${upstream_path}")"
        }
        git fetch upstream
        if [[ "${next_repo}" != "None" ]]; then
            git remote -v | grep next || {
                git remote add next "../$(basename "${next_path}")"
            }
            git fetch next
        fi
        popd >/dev/null || return 1
    else
        git clone "${repository}" "${destdir}"
        pushd "${destdir}" >/dev/null || return 1
        git checkout -b "${branch}" "origin/${branch}"
        git remote add upstream "../$(basename "${upstream_path}")"
        git fetch upstream
        if [[ "${next_repo}" != "None" ]]; then
            git remote add next "../$(basename "${next_path}")"
            git fetch next
        fi
        popd >/dev/null || return 1
    fi
}

if [[ "${next_repo}" != "None" ]]; then
    clone_simple "${next_path}" "${next_repo}" "force"
fi

clone_complex "${chromeos_path}" "${chromeos_repo}" "${rebase_baseline_branch}"

if [[ "${android_repo}" != "None" ]]; then
    clone_complex "${android_path}" "${android_repo}" "${android_baseline_branch}"
fi

# Remove and re-create all databases (for now) except upstream database.
rm -f "${rebasedb}" "${nextdb}"

echo "Initializing database"
./initdb.py

echo "Initializing upstream database"
./initdb-upstream.py

if [[ "${next_repo}" != "None" ]]; then
    echo "Initializing next database"
    ./initdb-next.py
fi

echo "Updating rebase database with upstream commits"
./update.py

echo "Calculating initial revert list"
./revertlist.py
echo "Calculating initial drop list"
./drop.py
echo "Calculating replace list"
./upstream.py
echo "Calculating topics"
./topics.py

./rebase_setup.py
