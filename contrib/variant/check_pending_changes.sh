#!/bin/bash
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

check_pending_changes() {
  # Check if there are pending changes in this repo, and if so, exit with
  # an error.
  #
  # Usage: check_pending_changes ${DIR}

  local DIR="$1"

  # Check for local modifications and warn the user to stash or revert.
  # Porcelain v2 format uses a '1' for changes, '2' for renames, and 'u'
  # for unmerged.
  if git status --porcelain=v2 --branch | grep -q "^[12u]" ; then
    MSG=$(echo "You have uncommitted changes in ${DIR}

Please stash or revert these changes, then re-run this program." | fmt -w 80)
   cat <<EOF >&2
******************************************************************************
${MSG}
******************************************************************************
EOF
    return 1
  fi

  # We usually want to track the upstream, but if NEW_VARIANT_WIP=1, then we
  # want to create new branches from our current HEAD and not from the
  # upstream-tracking branch. Check for this variable first, and if it's
  # set to 1, then allow the calling script to continue.

  # ${var:-0} assigns a value of 0 if the variable is not set.
  if [[ "${NEW_VARIANT_WIP:-0}" == 1 ]] ; then
    return 0
  fi

  pushd "${DIR}"

  # Check that we are tracking the upstream, and if not, ask the user
  # to checkout upstream or use NEW_VARIANT_WIP=1.
  if git status --porcelain=v2 --branch | grep -q "branch\.ab" ; then
    MSG=$(echo "Your local tree is ahead of the upstream by 1 or more commits.
You probably don't want to base the new variant on this branch, so please check
out the upstream branch in ${DIR} and then re-run this program.

If you want to base the new variant on the current branch, set NEW_VARIANT_WIP=1
in your environment and re-run this program." | fmt -w 80)
   cat <<EOF >&2
******************************************************************************
${MSG}
******************************************************************************
EOF
    return 1
  fi

  popd
  return 0
}
