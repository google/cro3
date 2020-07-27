#!/bin/bash
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

VERSION="1.0.2"
SCRIPT=$(basename -- "${0}")

export LC_ALL=C

if [[ ! -e /etc/cros_chroot_version ]]; then
  echo "This script must be run inside the chroot."
  exit 1
fi

if [[ "$#" -lt 3 ]]; then
  echo "Usage: ${SCRIPT} base_name reference_name variant_name [bug_number]"
  echo "e.g. ${SCRIPT} hatch hatch kohaku b:140261109"
  echo "e.g. ${SCRIPT} zork trembyle frobozz b:148161697"
  echo "Copies the cras config from the reference board to the new variant"
  exit 1
fi

# shellcheck source=revbump_ebuild.sh
# shellcheck disable=SC1091
source "${BASH_SOURCE%/*}/revbump_ebuild.sh"

# shellcheck source=check_standalone.sh
# shellcheck disable=SC1091
source "${BASH_SOURCE%/*}/check_standalone.sh"

# This is the name of the base board.
# ${var,,} converts to all lowercase.
BASE="${1,,}"
# This is the name of the reference board that we're using to make the variant.
# ${var,,} converts to all lowercase.
REFERENCE="${2,,}"
# ${var^} capitalizes first letter only.
REFERENCE_CAPITALIZED="${REFERENCE^}"
# This is the name of the variant that is being cloned.
VARIANT="${3,,}"
VARIANT_CAPITALIZED="${VARIANT^}"

# Assign BUG= text, or "None" if that parameter wasn't specified.
BUG=${4:-None}

cd "${HOME}/trunk/src/overlays/overlay-${BASE}/chromeos-base/chromeos-bsp-${BASE}/files/cras-config" || exit 1

# Start a branch. Use YMD timestamp to avoid collisions.
DATE=$(date +%Y%m%d)
BRANCH="create_${VARIANT}_${DATE}"
repo start "${BRANCH}" . || exit 1

# ebuild will be located 2 directories up.
pushd ../.. || exit 1
revbump_ebuild
popd || exit 1

mkdir "${VARIANT_CAPITALIZED}"
cp "${REFERENCE_CAPITALIZED}"/* "${VARIANT_CAPITALIZED}"
git add "${VARIANT_CAPITALIZED}"
git commit -m "${BASE}: Add ${VARIANT} cras config

Create a new cras config for the ${VARIANT} variant as a
copy of the ${REFERENCE} reference board's cras config.

(Auto-Generated by ${SCRIPT} version ${VERSION}).

BUG=${BUG}
TEST=N/A"

check_standalone "$(pwd)" "${BRANCH}"
