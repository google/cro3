#!/bin/bash
# Copyright 2018 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Random helper utilities that scripts might want.

# Set up variables for text color output.
C_BOLD_RED=
C_BOLD_GREEN=
C_BOLD_YELLOW=
C_OFF=

# Only support the text color if we're outputting to TTY.
if [[ -t 1 ]]; then
  C_BOLD_RED='\e[1;31m'
  C_BOLD_GREEN='\e[1;32m'
  C_BOLD_YELLOW='\e[1;33m'
  C_OFF='\e[0m'
fi

# Show an info message.
info() {
  echo -e "${C_BOLD_GREEN}INFO: $*${C_OFF}"
}

# Show a warning message.
warn() {
  echo -e "${C_BOLD_YELLOW}WARNING: $*${C_OFF}"
}

# Show an error message.
error() {
  echo -e "${C_BOLD_RED}ERROR: $*${C_OFF}" >&2
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
