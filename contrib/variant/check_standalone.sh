#!/bin/bash
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

check_standalone() {
  # Require that the script is running from new_variant.py, or that
  # $(NEW_VARIANT_STANDALONE} == 1. Otherwise, print an error message
  # and exit with an error code.
  #
  # Usage: check_standalone

  # ${var:-0} assigns a value of 0 if the variable is not set.
  if [[ "${NEW_VARIANT_STANDALONE:-0}" == 1 ]] ; then
    return 0
  fi

  local PARENT="$(ps --no-headers -o command "${PPID}")"

  if ! [[ "${PARENT}" =~ "new_variant" ]] ; then
    cat <<EOF >&2
******************************************************************************

This script appears to be running stand-alone, instead of under the control
of new_variant.py. You should be using new_variant.py instead. Please see
the documentation in src/platform/dev/contrib/variant/README.md.

If you really, really, REALLY want to run this script stand-alone, then
set NEW_VARIANT_STANDALONE=1 in the environment before running this script.

******************************************************************************
EOF
    return 1
  fi

  return 0
}
