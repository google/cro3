#!/bin/bash
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

VERSION="2.1.1"
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
  echo "Adds a new coreboot configuation for the variant by copying the"
  echo "baseboard config file and replaces the names in the config file."
  exit 1
fi

# This is the name of the base board.
# ${var,,} converts to all lowercase.
BASE="${1,,}"
# This is the name of the reference board that we're using to make the variant.
# ${var,,} converts to all lowercase.
REFERENCE="${2,,}"
# This is the name of the variant that is being cloned.
VARIANT="${3,,}"
# We need all uppercase version, too, so ${var^^}
REFERENCE_UPPER="${REFERENCE^^}"
VARIANT_UPPER="${VARIANT^^}"

# Assign BUG= text, or "None" if that parameter wasn't specified.
BUG=${4:-None}

# Work in third_party/chromiumos-overlay/sys-boot/coreboot/files/configs
# unless CB_CONFIG_DIR is set, in which case work in that dir
DEFAULT_CB_CONFIG_DIR="third_party/chromiumos-overlay/sys-boot/coreboot/files/configs"
cd "${HOME}/trunk/src/${CB_CONFIG_DIR:-${DEFAULT_CB_CONFIG_DIR}}" || exit 1

# Make sure the variant doesn't already exist.
if [[ -e "config.${VARIANT}" ]]; then
  echo "config.${VARIANT} already exists."
  echo "Have you already created this variant?"
  exit 1
fi

# Start a branch. Use YMD timestamp to avoid collisions.
DATE=$(date +%Y%m%d)
repo start "create_${VARIANT}_${DATE}" . || exit 1

# There are multiple usages of the reference board name that we want to change,
# using the Hatch reference board and the Kohaku variant in this example.
#   CONFIG_BOARD_GOOGLE_HATCH=y
#   ---
#   CONFIG_BOARD_GOOGLE_KOHAKU=y
# That one is easy; replace all-uppercase of the reference board with
# all-uppercase of the variant.
# Some baseboards have additional usages, such as
#   CONFIG_IFD_BIN_PATH="3rdparty/blobs/baseboard/hatch/descriptor-hatch.bin"
#   ---
#   CONFIG_IFD_BIN_PATH="3rdparty/blobs/baseboard/hatch/descriptor-kohaku.bin"
# The "hatch" name occurs twice in the original path, and we only want to
# change the last occurrence, so we get 'descriptor-kohaku.bin'.
#
# Another possibility for the IFD is that the baseboard doesn't use a
# hyphenated name, so we also need to search for descriptor.bin, e.g.
#   CONFIG_IFD_BIN_PATH="3rdparty/blobs/baseboard-octopus/descriptor.bin"
#
# We also need to update the me.bin name, so that each board has its own binary
#   CONFIG_ME_BIN_PATH="3rdparty/blobs/baseboard/hatch/me-hatch.bin"
#   ---
#   CONFIG_ME_BIN_PATH="3rdparty/blobs/baseboard/hatch/me-kohaku.bin"
sed -e "s/${REFERENCE_UPPER}/${VARIANT_UPPER}/" \
    -e "s/descriptor-${BASE}\.bin/descriptor-${VARIANT}.bin/" \
    -e "s/descriptor-${REFERENCE}\.bin/descriptor-${VARIANT}.bin/" \
    -e "s/descriptor\.bin/descriptor-${VARIANT}.bin/" \
    -e "s/me-${BASE}\.bin/me-${VARIANT}.bin/" \
    -e "s/me-${REFERENCE}\.bin/me-${VARIANT}.bin/" \
    "config.${REFERENCE}" > "config.${VARIANT}"
git add "config.${VARIANT}"

# Now commit the files.
git commit -m "${BASE}: Add ${VARIANT} coreboot configuration

Create a new coreboot configuration for the ${VARIANT} variant
of the ${REFERENCE} reference board. The new configuration file is
a copy of the reference board, but the name of the baseboard is
replaced by the name of the variant where applicable.

(Auto-Generated by ${SCRIPT} version ${VERSION}).

BUG=${BUG}
TEST=FW_NAME=${VARIANT} emerge-${BASE} coreboot chromeos-bootimage
Ensure that image-${VARIANT}.*.bin are created"
