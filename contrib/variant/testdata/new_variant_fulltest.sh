#!/bin/bash
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# End-to-end test of creating firmware for a new variant of a reference board
VERSION="1.1.0"
SCRIPT=$(basename -- "${0}")
set -e

export LC_ALL=C

if [[ ! -e /etc/cros_chroot_version ]]; then
  echo "This script must be run inside the chroot."
  exit 1
fi

if [[ "$#" -lt 1 ]]; then
  echo "Usage: ${SCRIPT} reference_name"
  echo "e.g. ${SCRIPT} hatch | puff | volteer2 | waddledee | waddledoo | lalala | trembyle | dalboz | brya0 | guybrush | nereid | nivviks | geralt | rex0"
  echo "End-to-end test to create a new variant of a reference board"
  echo "Script version ${VERSION}"
  exit 1
fi

# ${var,,} converts to all lowercase.
REFERENCE="${1,,}"

# Support for depthcharge variants was added later, so the default is no support
SUPPORTS_DC_VARIANT=0

# Support detachable form factor to prevent depthcharge emerge fail
SUPPORTS_DETACHABLE=0

# ebuild for all boards that use Boxster config
EBUILD=chromeos-config-bsp-private-9999.ebuild

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
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-puff-private/chromeos-base/chromeos-config-bsp-private
    FITIMAGE=puff
    FITIMAGE_OUTPUTS_DIR=/mnt/host/source/src/private-overlays/baseboard-puff-private/sys-boot/coreboot-private-files-puff/asset_generation/outputs
    FITIMAGE_FILES_DIR=/mnt/host/source/src/private-overlays/baseboard-puff-private/sys-boot/coreboot-private-files-puff/files
    ;;

  volteer2)
    BASE=volteer
    NEW=gnastygnorc
    CONFIG_DIR=/mnt/host/source/src/project/volteer
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-volteer-private/chromeos-base/chromeos-config-bsp-private
    FITIMAGE=volteer2
    FITIMAGE_OUTPUTS_DIR=/mnt/host/source/src/private-overlays/baseboard-volteer-private/sys-boot/coreboot-private-files-baseboard-volteer/files/blobs
    FITIMAGE_FILES_DIR=/mnt/host/source/src/private-overlays/baseboard-volteer-private/sys-boot/coreboot-private-files-baseboard-volteer/files
    ;;

  waddledee|waddledoo)
    BASE=dedede
    NEW=kingitchy
    CONFIG_DIR=/mnt/host/source/src/project/dedede
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-dedede-private/chromeos-base/chromeos-config-bsp-private
    FITIMAGE=drawcia
    # FITIMAGE_OUTPUTS_DIR and FITIMAGE_FILES_DIR are supposed to be the same;
    # gen_fit_image.sh moves the generated files from asset_generation/outputs
    # to files/blobs, so we have to put our fake fitimage files in files/blobs
    # for commit_fitimage.sh to find there.
    FITIMAGE_OUTPUTS_DIR=/mnt/host/source/src/private-overlays/baseboard-dedede-private/sys-boot/coreboot-private-files-baseboard-dedede/files/blobs
    FITIMAGE_FILES_DIR=/mnt/host/source/src/private-overlays/baseboard-dedede-private/sys-boot/coreboot-private-files-baseboard-dedede/files/blobs
    ;;

  lalala)
    BASE=keeby
    NEW=kingitchy
    CONFIG_DIR=/mnt/host/source/src/project/keeby
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-keeby-private/chromeos-base/chromeos-config-bsp-private
    FITIMAGE=lalala
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
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-zork-private/chromeos-base/chromeos-config-bsp-private
    ;;

  brya0)
    BASE=brya
    NEW=eris
    CONFIG_DIR=/mnt/host/source/src/project/brya
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-brya-private/chromeos-base/chromeos-config-bsp-private
    FITIMAGE=brya0
    FITIMAGE_OUTPUTS_DIR=/mnt/host/source/src/private-overlays/baseboard-brya-private/sys-boot/coreboot-private-files-baseboard-brya/files/blobs
    FITIMAGE_FILES_DIR=/mnt/host/source/src/private-overlays/baseboard-brya-private/sys-boot/coreboot-private-files-baseboard-brya/files
    SUPPORTS_DC_VARIANT=1
    ;;

  guybrush)
    BASE=guybrush
    NEW=jojo
    CONFIG_DIR=/mnt/host/source/src/project/guybrush
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-guybrush-private/chromeos-base/chromeos-config-bsp-private
    SUPPORTS_DC_VARIANT=1
    ;;

  nereid|nivviks)
    BASE=nissa
    NEW=eris
    CONFIG_DIR=/mnt/host/source/src/project/nissa
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-nissa-private/chromeos-base/chromeos-config-bsp-private
    FITIMAGE=nivviks
    FITIMAGE_OUTPUTS_DIR=/mnt/host/source/src/private-overlays/chipset-adln-private/sys-boot/coreboot-private-files-chipset-adln/files/blobs
    FITIMAGE_FILES_DIR=/mnt/host/source/src/private-overlays/chipset-adln-private/sys-boot/coreboot-private-files-chipset-adln/files
    USE_ZEPHYR=1
    ;;

  geralt)
    BASE=geralt
    NEW=whiteorchard
    CONFIG_DIR=/mnt/host/source/src/project/geralt
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-geralt-private/chromeos-base/chromeos-config-bsp-private
    USE_ZEPHYR=1
    SUPPORTS_DETACHABLE=1
    ;;

  rex0)
    BASE=rex
    NEW=eris
    CONFIG_DIR=/mnt/host/source/src/project/rex
    OVERLAY_DIR=/mnt/host/source/src/private-overlays/overlay-rex-private/chromeos-base/chromeos-config-bsp-private
    FITIMAGE=rex0
    FITIMAGE_OUTPUTS_DIR=/mnt/host/source/src/private-overlays/baseboard-rex-private/sys-boot/coreboot-private-files-baseboard-rex/files/blobs
    FITIMAGE_FILES_DIR=/mnt/host/source/src/private-overlays/baseboard-rex-private/sys-boot/coreboot-private-files-baseboard-rex/files
    SUPPORTS_DC_VARIANT=1
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
  if [[ -n ${OVERLAY_DIR+x} ]] ; then
    pushd "${OVERLAY_DIR}"
    git restore "${EBUILD}"
    popd
  fi
  # If we have a Boxster config dir, remove it
  if [[ -n ${CONFIG_DIR+x} ]] ; then
    pushd "${CONFIG_DIR}"
    rm -Rf "${NEW}"
    popd
  fi
  # If we have a fitimage, remove any files we created to fake out the
  # fitimage for the new variant.
  if [[ -n ${FITIMAGE_OUTPUTS_DIR+x} ]] ; then
    pushd "${FITIMAGE_OUTPUTS_DIR}"
    rm -f "fitimage-${NEW}.bin" "fitimage-${NEW}-versions.txt"
    rm -f "me_rw-${NEW}.bin"
    # Clean up the extra Volteer fitimage files, too.
    if [[ "${REFERENCE}" == "volteer2" ]] ; then
      rm -f "fit-${NEW}.log"
      popd
      pushd "${FITIMAGE_FILES_DIR}/blobs"
      rm -f "csme-${NEW}.bin" "descriptor-${NEW}.bin" "me_rw-${NEW}.bin"
      popd
      pushd "${FITIMAGE_FILES_DIR}/versions"
      rm -f "fitimage-${NEW}-versions.txt"
      popd
      pushd "${FITIMAGE_FILES_DIR}/logs"
      rm -f "fit-${NEW}-ro.log" "fit-${NEW}-rw.log"
      popd
      pushd "${FITIMAGE_FILES_DIR}/maps"
      rm -f "fitimage-${NEW}.map"
    fi
    # Clean up the extra Brya fitimage files, too.
    if [[ "${REFERENCE}" == "brya0" || "${REFERENCE}" == "nereid" || "${REFERENCE}" == "nivviks" || "${REFERENCE}" == "rex0" ]] ; then
      pushd "${FITIMAGE_FILES_DIR}/blobs"
      rm -f "csme-${NEW}.bin"
      rm -f "descriptor-${NEW}.bin"
      rm -f "me_rw-${NEW}.bin"
      popd
      pushd "${FITIMAGE_FILES_DIR}/metadata"
      rm -f "mfitimage-${NEW}-versions.txt"
      rm -f "mfitimage-${NEW}.map"
      rm -f "mfit_config_${NEW}.xml"
    fi
    popd
  fi
  # If new_variant didn't clean up after itself, the build must have failed.
  # Clean up with --abort and exit this script with an error code.
  if [[ -e "${HOME}/.new_variant.yaml" ]] ; then
    "${VARIANT_DIR}/new_variant.py" --abort --verbose
    exit 1
  fi
}
trap 'cleanup' EXIT

# Make sure we don't upload any CLs that are generated.
sed -i -z -E -f testdata/modify_step_list.sed "${REFERENCE}.py"

# Add the new variant to the overlay ebuild, if defined.
if [[ -n ${OVERLAY_DIR+x} ]] ; then
  pushd "${OVERLAY_DIR}"
  sed -i -E -e "s/PROJECTS=\(/PROJECTS=\(\n\t\"${NEW}\"/" "${EBUILD}"
  popd
fi

# Explicitly set the desired firmware targets (if SUPPORTS_DC_VARIANT is 1)
BUILD_TARGETS_SED="s/_FW_BUILD_CONFIG = None/_FW_BUILD_CONFIG = sc.create_fw_build_config(sc.create_fw_build_targets(\
coreboot='${NEW}',\
depthcharge='${NEW}',\
libpayload='${BASE}',\
ec='${NEW}'))\n/"

# If using zephyr, replace ec with zephyr_ec in fw build config.
if [[ ${USE_ZEPHYR} -eq 1 ]] ; then
  BUILD_TARGETS_SED=${BUILD_TARGETS_SED/ec=/zephyr_ec=}
fi

# Create the project configuration repo, if defined.
if [[ -n ${CONFIG_DIR+x} ]] ; then
  mkdir -p "${CONFIG_DIR}/${NEW}"
  pushd /mnt/host/source/src/config
  sbin/gen_project  /mnt/host/source/src/config "${BASE}" "/mnt/host/source/src/program/${BASE}/" "${NEW}" "${CONFIG_DIR}/${NEW}"
  popd
  # Because this isn't actually a git repo synced from the server, we can't
  # do any `git` or `repo` commands inside it, which means we can't run
  # fw_build_config.sh to make the changes we need. Instead just apply the
  # changes manually.
  pushd "${CONFIG_DIR}/${NEW}"

  if [[ ${SUPPORTS_DETACHABLE} -eq 1 ]] ; then
    sed -i -e "s/CLAMSHELL/DETACHABLE/g" config.star
  fi

  if [[ ${SUPPORTS_DC_VARIANT} -eq 1 ]] ; then
    # Load sw_config.star and update FW_BUILD_CONFIG to new project and build the config
    sed -i '4s/^/load("\/\/config\/util\/sw_config.star",sc="sw_config")\n/' config.star
    sed -i -e "${BUILD_TARGETS_SED}" config.star
  else
      # Use the same build target for everything
      sed -i -e "s/_FW_BUILD_CONFIG = None/_FW_BUILD_CONFIG = program.firmware_build_config(_${NEW_UPPER})/" config.star
  fi
  ./config.star
  popd
fi

# If we have a fitimage, make a copy of the reference board's fitimage under
# the new variant's name so that we don't have to generate the fitimage outside
# the chroot.
if [[ -n ${FITIMAGE_OUTPUTS_DIR+x} ]] ; then
  # Volteer requires some extra files; the FIT log is named after the
  # variant, and there are other blobs that are customized to the
  # variant and have names to reflect it. Volteer also does not use
  # fitimage-${VARIANT}.bin.
  if [[ "${REFERENCE}" == "volteer2" ]] ; then
    pushd "${FITIMAGE_FILES_DIR}/blobs"
    cp "csme-${FITIMAGE}.bin" "csme-${NEW}.bin"
    cp "descriptor-${FITIMAGE}.bin" "descriptor-${NEW}.bin"
    cp "me_rw-${FITIMAGE}.bin" "me_rw-${NEW}.bin"
    popd
    pushd "${FITIMAGE_FILES_DIR}/versions"
    cp "fitimage-${REFERENCE}-versions.txt" "fitimage-${NEW}-versions.txt"
    popd
    pushd "${FITIMAGE_FILES_DIR}/logs"
    cp "fit-${REFERENCE}-ro.log" "fit-${NEW}-ro.log"
    cp "fit-${REFERENCE}-rw.log" "fit-${NEW}-rw.log"
    popd
    pushd "${FITIMAGE_FILES_DIR}/maps"
    cp "fitimage-${REFERENCE}.map" "fitimage-${NEW}.map"
  elif [[ "${REFERENCE}" == "brya0" || "${REFERENCE}" == "nereid" || "${REFERENCE}" == "nivviks" || "${REFERENCE}" == "rex0" ]] ; then
    pushd "${FITIMAGE_OUTPUTS_DIR}"
    cp "csme-${FITIMAGE}.bin" "csme-${NEW}.bin"
    cp "descriptor-${FITIMAGE}.bin" "descriptor-${NEW}.bin"
    cp "me_rw-${FITIMAGE}.bin" "me_rw-${NEW}.bin"
    popd
    pushd "${FITIMAGE_FILES_DIR}/metadata"
    cp "mfitimage-${REFERENCE}-versions.txt" "mfitimage-${NEW}-versions.txt"
    cp "mfitimage-${REFERENCE}.map" "mfitimage-${NEW}.map"
    cp "mfit_config_${REFERENCE}.xml" "mfit_config_${NEW}.xml"
  else
    pushd "${FITIMAGE_OUTPUTS_DIR}"
    # All boards that have fitimages and are not volteer or brya use a fitimage binary.
    cp "${FITIMAGE_FILES_DIR}/fitimage-${FITIMAGE}.bin" "fitimage-${NEW}.bin"
    cp "${FITIMAGE_FILES_DIR}/fitimage-${FITIMAGE}-versions.txt" "fitimage-${NEW}-versions.txt"
    # Dedede boards also need an me_rw-${VARIANT}.bin
    if [[ "${REFERENCE}" == "waddledee" || "${REFERENCE}" == "waddledoo" || "${REFERENCE}" == "lalala" ]] ; then
      cp "${FITIMAGE_FILES_DIR}/me_rw-${FITIMAGE}.bin" "me_rw-${NEW}.bin"
    fi
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
