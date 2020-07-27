#!/bin/bash
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

check_standalone() {
  # Check if this script is running from new_variant.py, and if not, print
  # a message informing the user that they have the option to back out and
  # run the process from new_variant.py.
  #
  # Usage: check_standalone ${DIR} ${BRANCH}

  local DIR="$1"
  local BRANCH="$2"

  local PARENT
  PARENT="$(ps --no-headers -o command "${PPID}")"

  if ! [[ "${PARENT}" =~ "new_variant" ]] ; then
    cat <<EOF >&2
******************************************************************************

This script appears to be running stand-alone, instead of under the control
of new_variant.py. If you want to continue using the scripts by themselves,
you can do that.

However, there are significant advantages to using new_variant.py: it will
call the right scripts in the right order, upload CLs, and even add
Cq-Depend information to them so they submit in the correct order. If you
haven't uploaded any of your CLs, you can start over with new_variant.py,
but you'll need to delete your CLs for the new variant.

To delete the CL that this script just created:
  pushd ${DIR}
  repo abandon ${BRANCH} .
  popd

Please refer to the README.md file in platform/dev/contrib/variant for
details about using new_variant.py to create all of the CLs required for
a new variant.

******************************************************************************
EOF
  fi
}
