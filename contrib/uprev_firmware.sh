#!/bin/bash
# Copyright 2017 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Script to automate firmware update process for a board.
# It works only when the private overlay and firmware ebuild
# file for the board are already in place.

# Loads script libraries.
CONTRIB_DIR=$(dirname "$(readlink -f "$0")")
. "${CONTRIB_DIR}/common.sh" || exit 1

# Flags.
DEFINE_string board "${DEFAULT_BOARD}" "Which board the firmware is for" b
DEFINE_string fw_version "" "Firmware version of the new firmware" v
DEFINE_string output_dir "" "Output directory" o
DEFINE_boolean rw_only "${FLAGS_FALSE}" "Only update RW image"
DEFINE_boolean dev "${FLAGS_FALSE}" "Use image.dev.bin as the main firmware binary"

FLAGS_HELP="Update chromeos-firmware-${board} ebuild file and tarball in BCS for the new firmware.

USAGE: $0 [flags] args

For example:

To uprev kevin ro/rw firmware to 8785.178.0, run:
$ ./uprev_firmware -b kevin -v 8785.178.0

To uprev chell rw firmware to 7820.288.0, run:
$ ./uprev_firmware -b chell -v 7820.288.0 --rw_only
"

# Parse command line.
FLAGS "$@" || exit 1
eval set -- "${FLAGS_ARGV}"
set -e

# Script must run inside the chroot.
assert_inside_chroot

# Sanity check the arguments and initialize global variables.
init() {
  TMP=$(mktemp -d --suffix=.uprev_firmware)

  if [[ -z "${FLAGS_board}" ]]; then
    die "-b or --board required."
  fi

  # Uppercase the 1st letter of the board name.
  BOARD_NAME=${FLAGS_board^}

  if [[ -z "${FLAGS_fw_version}" ]]; then
    die "Please specify a firmware version using -v"
  fi

  if [[ -z "${FLAGS_output_dir}" ]]; then
    info "${TMP} is used as your default output directory\n"
    FLAGS_output_dir=${TMP}
  fi

  if [[ ! -d "${FLAGS_output_dir}" ]]; then
    die "The output directory does not exist\n"
  fi
  FLAGS_output_dir=$(realpath "${FLAGS_output_dir}")

  if [[ ! -d "/build/${FLAGS_board}" ]]; then
    die "Please setup board for ${FLAGS_board} first"
  fi

  OVERLAY_DIR="${GCLIENT_ROOT}/src/private-overlays/\
overlay-${FLAGS_board}-private"
  if [[ ! -d "${OVERLAY_DIR}" ]]; then
    die "The private overlay is not found: ${OVERLAY_DIR}"
  fi

  EBUILD_DIR="${OVERLAY_DIR}/chromeos-base/chromeos-firmware-${FLAGS_board}"
  if [[ ! -d "${EBUILD_DIR}" ]]; then
    die "The directory doesn't exist: ${EBUILD_DIR}"
  fi

  EBUILD_FILE="${EBUILD_DIR}/chromeos-firmware-${FLAGS_board}-9999.ebuild"
  if [[ ! -f "${EBUILD_FILE}" ]]; then
    die "Please create the initial firmware ebuild manually:\n" \
      "${EBUILD_FILE}"
  fi

  if [[ "${FLAGS_dev}" -eq "${FLAGS_TRUE}" ]]; then
    MAIN_FW_TAR_NAME="${BOARD_NAME}.${FLAGS_fw_version}.DEV_IMAGE_DO_NOT_SHIP\
.tbz2"
  else
    MAIN_FW_TAR_NAME="${BOARD_NAME}.${FLAGS_fw_version}.tbz2"
  fi
  EC_FW_TAR_NAME="${BOARD_NAME}_EC.${FLAGS_fw_version}.tbz2"
  PD_FW_TAR_NAME="${BOARD_NAME}_PD.${FLAGS_fw_version}.tbz2"
}

# Clean up function when exit.
cleanup() {
  rm -rf "${TMP}"
}

# Prepare new firmware tarballs to upload to BCS
prepare_fw_tarball() {
  local build_dir="gs://chromeos-releases/canary-channel/\
${FLAGS_board}/${FLAGS_fw_version}"
  local build_fw_tar_path=$(gsutil ls "${build_dir}/ChromeOS-firmware-*")
  local build_fw_tar_name=$(basename "${build_fw_tar_path}")

  if [[ -z "${build_fw_tar_path}" ]]; then
    die "Please ensure your gsutil works and the firmware version is correct"
  fi

  # Download the firmware tarball.
  gsutil cp "${build_fw_tar_path}" "${TMP}/."
  tar -xvf "${TMP}/${build_fw_tar_name}" -C "${TMP}"
  if [[ "${FLAGS_dev}" -eq "${FLAGS_TRUE}" ]]; then
    mv "${TMP}/image.dev.bin" "${TMP}/image.bin"
    warn "You are uploading a developer image with serial output." \
      "Please only do this during early bring-up. Dogfooding should always be" \
      "done with production images since timing differences in developer"\
      "images can hide bugs and the production image must be sufficiently" \
      "tested before shipping.\n"
  fi
  # Make new tarballs for EC/AP FW binaries.
  tar -jcvf "${TMP}/${MAIN_FW_TAR_NAME}" -C "${TMP}" image.bin
  if [[ "${FLAGS_rw_only}" -eq "${FLAGS_FALSE}" ]]; then
    tar -jcvf "${TMP}/${EC_FW_TAR_NAME}" -C "${TMP}" ec.bin
    # Do this for PD FW as well (if available).
    if [ -d "${TMP}/${FLAGS_board}_pd" ]; then
      tar -jcvf "${TMP}/${PD_FW_TAR_NAME}" -C "${TMP}/${FLAGS_board}_pd" ec.bin
    else
      PD_FW_TAR_NAME=
    fi
  fi

  if [[ "${TMP}" != "${FLAGS_output_dir}" ]]; then
    mv "${TMP}/${MAIN_FW_TAR_NAME}" "${FLAGS_output_dir}"
    if [[ "${FLAGS_rw_only}" -eq "${FLAGS_FALSE}" ]]; then
      mv "${TMP}/${EC_FW_TAR_NAME}" "${FLAGS_output_dir}"
      if [[ -z "${PD_FW_TAR_NAME}" ]]; then
        mv "${TMP}/${PD_FW_TAR_NAME}" "${FLAGS_output_dir}"
      fi
    fi
  fi

  local file_list="${FLAGS_output_dir}/${MAIN_FW_TAR_NAME}\n"
  if [[ "${FLAGS_rw_only}" -eq "${FLAGS_FALSE}" ]]; then
    file_list+=" ${FLAGS_output_dir}/${EC_FW_TAR_NAME}\n"
    if [ -n "${PD_FW_TAR_NAME}" ]; then
      file_list+=" ${FLAGS_output_dir}/${PD_FW_TAR_NAME}\n"
    fi
  fi

  info "Your tarballs are ready at\n" \
    "${file_list}" \
    "To continue, please upload them to BCS manually through CPFE:\n" \
    "https://www.google.com/chromeos/partner/fe/#bcUpload:type=PRIVATE\n"
}

# Update the firmware ebuild file in the device private overlay
update_fw_ebuild() {
  local keyword_main_fw="MAIN_IMAGE=\"bcs:\/\/${BOARD_NAME}"
  local keyword_main_rw_fw="CROS_FIRMWARE_MAIN_RW_IMAGE="
  local keyword_ec_fw="EC_IMAGE=\"bcs:\/\/${BOARD_NAME}"
  local keyword_pd_fw="PD_IMAGE=\"bcs:\/\/${BOARD_NAME}"
  local main_fw_line=$(grep -i "${keyword_main_fw}" "${EBUILD_FILE}")
  local main_rw_fw_line=$(grep -i "${keyword_main_rw_fw}" "${EBUILD_FILE}")
  local ec_fw_line=$(grep -i "${keyword_ec_fw}" "${EBUILD_FILE}")
  local pd_fw_line=$(grep -i "${keyword_pd_fw}" "${EBUILD_FILE}")
  local old_main_fw_tar_name="${main_fw_line#*bcs://}"
  old_main_fw_tar_name="${old_main_fw_tar_name%'"'}"
  local old_ec_fw_tar_name="${ec_fw_line#*bcs://}"
  old_ec_fw_tar_name="${old_ec_fw_tar_name%'"'}"
  local old_pd_fw_tar_name="${pd_fw_line#*bcs://}"
  old_pd_fw_tar_name="${old_pd_fw_tar_name%'"'}"

  # Check if the repo is clean.
  local git_output="$(git --git-dir="${OVERLAY_DIR}/.git" \
    --work-tree="${OVERLAY_DIR}" status --porcelain)"
  if [[ -n ${git_output} ]]; then
    die "Please clean your repo first: ${OVERLAY_DIR}"
  fi

  # Update the fw ebuild file.
  if [[ -n "${main_rw_fw_line}" ]]; then
    sed -i "/${keyword_main_rw_fw}/d" "${EBUILD_FILE}"
  fi
  if [[ "${FLAGS_rw_only}" -eq "${FLAGS_FALSE}" ]]; then
    sed -i -e "s/${old_main_fw_tar_name}/${MAIN_FW_TAR_NAME}/" \
      -e "s/${old_ec_fw_tar_name}/${EC_FW_TAR_NAME}/" "${EBUILD_FILE}"
    main_rw_fw_line="${keyword_main_rw_fw}\"\""
    if [[ -n "${PD_FW_TAR_NAME}" ]]; then
      sed -i -e "s/${old_pd_fw_tar_name}/${PD_FW_TAR_NAME}/" \
        "${EBUILD_FILE}"
    fi
  else
    main_rw_fw_line="${keyword_main_rw_fw}\"\
bcs:\/\/${MAIN_FW_TAR_NAME}\""
  fi
  # Create a new line for CROS_FIRMWARE_MAIN_RW_IMAGE
  sed -i "/${keyword_main_fw}/a ${main_rw_fw_line}" "${EBUILD_FILE}"

  # Update the manifest.
  ebuild-"${FLAGS_board}" "${EBUILD_FILE}" manifest
  info "Ebuild files and manifest are updated at:\n${EBUILD_DIR}\n"
}

# Build the firmware updater and verify the firmware version
verify_fw_updater() {
  local fw_updater="/build/${FLAGS_board}/usr/sbin/chromeos-firmwareupdate"
  local fw_updater_bios_version
  cros_workon-"${FLAGS_board}" start "chromeos-firmware-${FLAGS_board}"
  emerge-"${FLAGS_board}" "chromeos-firmware-${FLAGS_board}"
  cros_workon-"${FLAGS_board}" stop "chromeos-firmware-${FLAGS_board}"
  if [[ ! -f "${fw_updater}" ]]; then
    die "Firmware updater is not found at ${fw_updater}"
  fi
  if [[ "${FLAGS_rw_only}" -eq "${FLAGS_TRUE}" ]]; then
    fw_updater_bios_version=$(${fw_updater} -V | grep "BIOS (RW) version")
  else
    fw_updater_bios_version=$(${fw_updater} -V | grep "BIOS version")
  fi
  fw_updater_bios_version="${fw_updater_bios_version#*Google_}"
  fw_updater_bios_version="${fw_updater_bios_version,,}"
  if [[ "${FLAGS_board}.${FLAGS_fw_version}" != \
    "${fw_updater_bios_version}" ]]; then
    die "The firmware version in the updater is incorrect"
  fi
  info "The firmware version in the updater is verified:" \
    "${FLAGS_fw_version}\nPlease commit your change.\n"
}

main() {
  TMP=""
  trap cleanup EXIT

  if [[ "$#" -ne 0 ]]; then
    flags_help
    exit 1
  fi

  init
  prepare_fw_tarball

  local sure
  read -p "Please confirm that you've uploaded the tarballs to BCS [y/N]:" sure
  if [[ "${sure}" != "y" ]]; then
    die "Aborted..."
  fi
  update_fw_ebuild
  verify_fw_updater
}

main "$@"
