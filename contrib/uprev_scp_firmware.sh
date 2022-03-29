#!/bin/bash
# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Script to automate SCP firmware update process for MTK boards.
# This script does the following steps:
# (1) Download the firmware tarball from chromeos-releases.
# (2) Pack the SCP firmware tarball.
# (3) Upload the new tarball to chromeos-localmirror and update the ebuild file.

# Loads script libraries.
CONTRIB_DIR=$(dirname "$(readlink -f "$0")")
. "${CONTRIB_DIR}/common.sh" || exit 1

# Flags.
DEFINE_string board "" "Which board the SCP firmware is for" b
DEFINE_string fw_version "" "The version of the new SCP firmware" v

FLAGS_HELP="Update chromeos-scp-firmware-{BOARD} ebuild file and upload the \
new SCP tarball to chromeos-localmirror.

USAGE: $0 [flags] args

For example:

$ ./uprev_scp_firmware -b kukui -v 12573.293.0
"

# Parse command line.
FLAGS "$@" || exit 1
eval set -- "${FLAGS_ARGV}"
set -e

# Script must run inside the chroot.
assert_inside_chroot

# Check the arguments and initialize global variables.
init() {
  TMP=$(mktemp -d --suffix=.uprev_scp_firmware)

  if [[ -z "${FLAGS_board}" ]]; then
    die "-b or --board required."
  fi

  if [[ -z "${FLAGS_fw_version}" ]]; then
    die "Please specify a firmware version using -v"
  fi

  OVERLAY_DIR="${GCLIENT_ROOT}/src/overlays/baseboard-${FLAGS_board}"
  if [[ ! -d "${OVERLAY_DIR}" ]]; then
    die "The baseboard overlay is not found: ${OVERLAY_DIR}"
  fi


  EBUILD_DIR="${OVERLAY_DIR}/chromeos-base/chromeos-scp-firmware-${FLAGS_board}"
  if [[ ! -d "${EBUILD_DIR}" ]]; then
    die "The directory doesn't exist: ${EBUILD_DIR}"
  fi

  local package_name="chromeos-scp-firmware-${FLAGS_board}-${FLAGS_fw_version}"
  OLD_EBUILD_FILE=\
"$(ls "${EBUILD_DIR}/chromeos-scp-firmware-${FLAGS_board}-"*.ebuild || true)"
  if [[ ! -f "${OLD_EBUILD_FILE}" ]]; then
    die "Please create the initial firmware ebuild manually:" \
      "${OLD_EBUILD_FILE}"
  fi
  NEW_EBUILD_FILE="${EBUILD_DIR}/${package_name}.ebuild"

  SCP_FW_TAR_NAME="${package_name}.tbz2"
}

# Clean up function when exit.
cleanup() {
  trap - INT TERM EXIT
  rm -rf "${TMP}"
  exit
}

# Download firmware tarball from chromeos-releases and pack the SCP firmware.
prepare_scp_fw_tarball() {
  local build_dir="gs://chromeos-releases/canary-channel/${FLAGS_board}/\
${FLAGS_fw_version}"
  local build_fw_tar_path
  local build_fw_tar_name

  build_fw_tar_path="$(gsutil ls "${build_dir}/ChromeOS-firmware-*")"
  build_fw_tar_name="$(basename "${build_fw_tar_path}")"

  if [[ -z "${build_fw_tar_path}" ]]; then
    die "Please ensure your gsutil works and the firmware version is correct"
  fi

  # Download the firmware tarball.
  gsutil cp "${build_fw_tar_path}" "${TMP}/."
  tar -xvf "${TMP}/${build_fw_tar_name}" -C "${TMP}"

  local scp_file_path="${FLAGS_board}_scp_private/scp.img"
  if [[ ! -f "${TMP}/${scp_file_path}" ]]; then
    die "The SCP firmware ${scp_file_path} does not exist in the given" \
      "version ${FLAGS_fw_version}."
  fi

  local scp_dir_name="chromeos-scp-firmware-${FLAGS_board}-${FLAGS_fw_version}"
  mkdir "${TMP}/${scp_dir_name}"
  mv "${TMP}/${FLAGS_board}_scp_private/scp.img" "${TMP}/${scp_dir_name}"

  tar cjf "${TMP}/${SCP_FW_TAR_NAME}" -C "${TMP}" "${scp_dir_name}"
}

# Upload the SCP firmware tarball to chrmoeos-localmirror and update the ebuild.
upload_to_localmirror() {
  gsutil cp "${TMP}/${SCP_FW_TAR_NAME}" gs://chromeos-localmirror/distfiles/
  gsutil acl ch -u AllUsers:R \
    gs://chromeos-localmirror/distfiles/"${SCP_FW_TAR_NAME}"

  # Update the ebuild Manifest
  mv -n "${OLD_EBUILD_FILE}" "${NEW_EBUILD_FILE}"
  ebuild "${NEW_EBUILD_FILE}" manifest
}

main() {
  TMP=""
  trap cleanup INT TERM EXIT

  if [[ "$#" -ne 0 ]]; then
    flags_help
    exit 1
  fi

  init
  prepare_scp_fw_tarball

  local sure
  read -r -p "The tarball will be uploaded to \
gs://chromeos-localmirror/distfiles/${SCP_FW_TAR_NAME}. \
Are you sure you want to continue? [y/N]:" sure
  if [[ "${sure}" != "y" ]]; then
    die "Aborted..."
  fi
  upload_to_localmirror

  echo "The Manifest and the ebuild file in ${EBUILD_DIR} has been updated. \
Please upload a CL to update the files manually."
}

main "$@"
