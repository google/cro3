#!/bin/bash
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# End-to-end test of creating firmware for a new variant of a reference board
VERSION="1.0.1"
SCRIPT=$(basename -- "${0}")
set -e

export LC_ALL=C

if [[ ! -e /etc/cros_chroot_version ]]; then
  echo "This script must be run inside the chroot."
  exit 1
fi

if [[ "$#" -lt 1 ]]; then
  echo "Usage: ${SCRIPT} reference_name"
  echo "e.g. ${SCRIPT} hatch | puff | volteer | waddledee | waddledoo | trembyle | dalboz"
  echo "End-to-end test to create a new variant of a reference board"
  echo "Script version ${VERSION}"
  exit 1
fi

# ${var,,} converts to all lowercase.
REFERENCE="${1,,}"

# Set variables depending on the reference board.
#
# All boards:
#
# BASE - the name of the baseboard.
# NEW - the name of the new variant.
#
# Boards using Boxtser config only:
#
# CONFIG_DIR - the directory for the project configuration files, if needed
#   for the baseboard.
# OVERLAY_DIR - the directory for the chromeos-config overlay ebuild, if it
#   needs to be modified for this baseboard so that the new variant will build.
# EBUILD - the name of the chromeos-config overlay ebuild, if needed.
#
# Intel-based reference boards only:
#
# FITIMAGE - the base name of the fitimage binary to copy for making a
#   fake fitimage for the new board. This will almost always be the same
#   as REFERENCE, but for Waddledee and Waddledoo, it will be Drawcia,
#   because Waddledee and Waddledoo have a 32 MB SPI ROM, while all the
#   other variants use 16 MB, so we need to use a 16 MB fitimage for
#   the build to succeed.
# FITIMAGE_OUTPUTS_DIR - the directory where gen_fit_image.sh will place
#   the fitimage files.
# FITIMAGE_FILES_DIR - the directory where commit_fitimage.sh moves (or copies)
#   the fitimage that gen_fit_image.sh created. This is where the reference
#   board's fitimage lives, and we will copy that fitimage and related files
#   to the new variant's name and place the copy in ${FITIMAGE_OUTPUTS_DIR}.
#
case "${REFERENCE}" in
  hatch)
    BASE=hatch
    NEW=tiamat
    FITIMAGE=hatch
    FITIMAGE_OUTPUTS_DIR=/mnt/host/source/src/private-overlays/baseboard-hatch-private/sys-boot/coreboot-private-files-hatch/asset_generation/outputs
    FITIMAGE_FILES_DIR=/mnt/host/source/src/private-overlays/baseboard-hatch-private/sys-boot/coreboot-private-files-hatch/files
    ;;

  puff)
    BASE=puff
    NEW=tiamat
    CONFIG_DIR=/mnt/host/source/src/project/puff
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-puff-private/chromeos-base/chromeos-config-bsp-puff-private
    EBUILD=chromeos-config-bsp-puff-private-9999.ebuild
    FITIMAGE=puff
    FITIMAGE_OUTPUTS_DIR=/mnt/host/source/src/private-overlays/baseboard-puff-private/sys-boot/coreboot-private-files-puff/asset_generation/outputs
    FITIMAGE_FILES_DIR=/mnt/host/source/src/private-overlays/baseboard-puff-private/sys-boot/coreboot-private-files-puff/files
    ;;

  volteer)
    BASE=volteer
    NEW=gnastygnorc
    CONFIG_DIR=/mnt/host/source/src/project/volteer
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-volteer-private/chromeos-base/chromeos-config-bsp-volteer-private
    EBUILD=chromeos-config-bsp-volteer-private-9999.ebuild
    FITIMAGE=volteer
    FITIMAGE_OUTPUTS_DIR=/mnt/host/source/src/private-overlays/baseboard-volteer-private/sys-boot/coreboot-private-files-baseboard-volteer/asset_generation/outputs
    FITIMAGE_FILES_DIR=/mnt/host/source/src/private-overlays/baseboard-volteer-private/sys-boot/coreboot-private-files-baseboard-volteer/files
    ;;

  waddledee|waddledoo)
    BASE=dedede
    NEW=kingitchy
    CONFIG_DIR=/mnt/host/source/src/project/dedede
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-dedede-private/chromeos-base/chromeos-config-bsp-dedede-private
    EBUILD=chromeos-config-bsp-dedede-private-9999.ebuild
    FITIMAGE=drawcia
    # FITIMAGE_OUTPUTS_DIR and FITIMAGE_FILES_DIR are supposed to be the same;
    # gen_fit_image.sh moves the generated files from asset_generation/outputs
    # to files/blobs, so we have to put our fake fitimage files in files/blobs
    # for commit_fitimage.sh to find there.
    FITIMAGE_OUTPUTS_DIR=/mnt/host/source/src/private-overlays/baseboard-dedede-private/sys-boot/coreboot-private-files-baseboard-dedede/files/blobs
    FITIMAGE_FILES_DIR=/mnt/host/source/src/private-overlays/baseboard-dedede-private/sys-boot/coreboot-private-files-baseboard-dedede/files/blobs
    ;;

  trembyle|dalboz)
    BASE=zork
    NEW=grue
    CONFIG_DIR=/mnt/host/source/src/project/zork
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-zork-private/chromeos-base/chromeos-config-bsp-zork-private
    EBUILD=chromeos-config-bsp-zork-private-9999.ebuild
    ;;

  *)
    echo Unsupported reference board "${REFERENCE}"
    exit 1
    ;;
esac

# ${var^^} converts to all uppercase.
NEW_UPPER="${NEW^^}"

VARIANT_DIR=/mnt/host/source/src/platform/dev/contrib/variant
pushd "${VARIANT_DIR}"

# When exiting for any reason, restore files under version control to their
# unmodified state and remove any new files that were created outside of
# version control.
# Not all of these steps may have happened yet, but we can silently ignore
# any errors with git trying to restore a file that hasn't changed, or `rm`
# trying to remove files that don't exist.
cleanup() {
  # Undo changes to the control file.
  pushd "${VARIANT_DIR}"
  git restore "${REFERENCE}.py"
  popd
  # If we have an ebuild, undo any changes.
  if [[ ! -z ${OVERLAY_DIR+x} ]] ; then
    pushd "${OVERLAY_DIR}"
    git restore "${EBUILD}"
    popd
  fi
  # If we have a Boxster config dir, remove it
  if [[ ! -z ${CONFIG_DIR+x} ]] ; then
    pushd "${CONFIG_DIR}"
    rm -Rf "${NEW}"
    popd
  fi
  # If we have a fitimage, remove any files we created to fake out the
  # fitimage for the new variant.
  if [[ ! -z ${FITIMAGE_OUTPUTS_DIR+x} ]] ; then
    pushd "${FITIMAGE_OUTPUTS_DIR}"
    rm -f "fitimage-${NEW}.bin" "fitimage-${NEW}-versions.txt"
    # Clean up the extra Volteer fitimage files, too.
    if [[ "${REFERENCE}" == "volteer" ]] ; then
      rm -f "fit-${NEW}.log"
      popd
      pushd "${FITIMAGE_FILES_DIR}/blobs"
      rm -f "csme-${NEW}.bin" "descriptor-${NEW}.bin"
    fi
    popd
  fi
  # If new_variant didn't clean up after itself, the build must have failed.
  # Clean up with --abort and exit this script with an error code.
  if [[ -e "${HOME}/.new_variant.yaml" ]] ; then
    ./new_variant.py --abort --verbose
    exit 1
  fi
}
trap 'cleanup' EXIT

# Make sure we don't upload any CLs that are generated.
sed -i -z -E -f testdata/modify_step_list.sed "${REFERENCE}.py"

# Add the new variant to the overlay ebuild, if defined.
if [[ ! -z ${OVERLAY_DIR+x} ]] ; then
  pushd "${OVERLAY_DIR}"
  sed -i -E -e "s/PROJECTS=\(/PROJECTS=\(\n\t\"${NEW}\"/" "${EBUILD}"
  popd
fi

# Create the project configuration repo, if defined.
if [[ ! -z ${CONFIG_DIR+x} ]] ; then
  mkdir -p "${CONFIG_DIR}/${NEW}"
  pushd /mnt/host/source/src/config
  sbin/gen_project  /mnt/host/source/src/config "${BASE}" "/mnt/host/source/src/program/${BASE}/" "${NEW}" "${CONFIG_DIR}/${NEW}"
  popd
  # Because this isn't actually a git repo synced from the server, we can't
  # do any `git` or `repo` commands inside it, which means we can't run
  # fw_build_config.sh to make the changes we need. Instead just apply the
  # changes manually.
  pushd "${CONFIG_DIR}/${NEW}"
  # Apply FW_BUILD_CONFIG to new project and build the config
  sed -i -e "s/_FW_BUILD_CONFIG = None/_FW_BUILD_CONFIG = program.firmware_build_config(_${NEW_UPPER})/" config.star
  ./config.star
  popd
fi

# If we have a fitimage, make a copy of the reference board's fitimage under
# the new variant's name so that we don't have to generate the fitimage outside
# the chroot.
if [[ ! -z ${FITIMAGE_OUTPUTS_DIR+x} ]] ; then
  pushd "${FITIMAGE_OUTPUTS_DIR}"
  cp "${FITIMAGE_FILES_DIR}/fitimage-${FITIMAGE}.bin" "fitimage-${NEW}.bin"
  cp "${FITIMAGE_FILES_DIR}/fitimage-${FITIMAGE}-versions.txt" "fitimage-${NEW}-versions.txt"
  # Volteer requires some extra files; the FIT log is named after the
  # variant, and there are two other blobs that are customized to the
  # variant and have names to reflect it.
  if [[ "${REFERENCE}" == "volteer" ]] ; then
    cp "fit-${FITIMAGE}.log" "fit-${NEW}.log"
    popd
    pushd "${FITIMAGE_FILES_DIR}/blobs"
    cp "csme-${FITIMAGE}.bin" "csme-${NEW}.bin"
    cp "descriptor-${FITIMAGE}.bin" "descriptor-${NEW}.bin"
  fi
  popd
fi

# This test uses Kingitchy as a new variant name for both Waddledee and
# Waddledoo. The EC build fails if you test creating a variant of one of
# those reference boards and then the other without cleaning up the build
# directory first, because the outputs in platform/ec/build/kingitchy don't
# match up with the "new" source files that are under the same name.
# To prevent old build outputs from colliding, just clean the EC build.
pushd /mnt/host/source/src/platform/ec
make clobber
popd

# Now create the new variant. Output will be captured as a side-effect of
# running in CQ, or it will be in the scrollback buffer on the user's terminal
# when executed locally.
# If the build fails, the cleanup handler will call new_variant.py --abort
# to clean up.
./new_variant.py --board="${REFERENCE}" --variant="${NEW}" --verbose
