#!/bin/bash
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Random helper utilities that scripts might want.

# Show an error message.
error() {
  echo "ERROR: $*" >&2
}

# Show an error message and exit.
die() {
  error "$*"
  exit 1
}

if [[ -z "${CONTRIB_DIR}" ]]; then
  die "Scripts must set CONTRIB_DIR first"
fi

# Load the shflags helper library.  Any script using us will probably have
# command line flags, and they should be using shflags to parse them.
source "${CONTRIB_DIR}/shflags" || die "Could not load shflags"

# Path to the repo checkout.
GCLIENT_ROOT="/mnt/host/source"
SRC_ROOT="${GCLIENT_ROOT}/src"

# Whether we're executing inside the cros_sdk chroot.
is_inside_chroot() {
  [[ -f "/etc/cros_chroot_version" ]]
}

# Fail unless we're inside the chroot.  This guards against messing up your
# workstation.
assert_inside_chroot() {
  if ! is_inside_chroot; then
    die "This script must be run inside the chroot.  Run this first: cros_sdk"
  fi
}
