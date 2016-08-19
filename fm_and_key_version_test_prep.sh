#!/bin/bash
# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Given a test image, a firmware version, and 5 modified firmware binaries
# this script will generate 5 auto update payloads with incremented OS
# and firmware versions.  The payloads can then be applied one after another
# to test firmware update and kernel version increments.

find_common_sh() {
  local thisdir="$(dirname "$(readlink -f "$0")")"
  local common_paths=(/usr/lib/crosutils "${thisdir}")
  local path

  SCRIPT_ROOT="${common_paths[0]}"
  for path in "${common_paths[@]}"; do
    if [ -r "${path}/common.sh" ]; then
      SCRIPT_ROOT="${path}"
      break
    fi
  done
}

find_common_sh
. "${SCRIPT_ROOT}/common.sh" || exit 1

cleanup() {
  "${SCRIPTS_DIR}/mount_gpt_image.sh" -u -r "$ROOT_FS_DIR" -s "$STATEFUL_FS_DIR"
}

on_exit() {
  cleanup
  if "${IS_ABORT}"; then
    error "Failed to generate all payloads."
  fi
}

replace_fmap_section() {
  local image="$1"
  local section="$2"
  local data="$3"

  # format: NAME OFFSET SIZE
  local info="$(dump_fmap -p "${image}" "${section}")"
  local name offset size
  read name offset size <<<"${info}"

  [ -n "${offset}" ] || die_notrace "Invalid firmware image: No ${section}."

  dd if=/dev/zero of="$image" bs=1 seek="${offset}" count="${size}" \
    conv=notrunc
  echo -n "${data}" | dd of="$image" bs=1 seek="${offset}" conv=notrunc
}

replace_firmware_id() {
  local image="$1"
  local new_id="$2"

  replace_fmap_section "${image}" RO_FRID "$new_id"
  replace_fmap_section "${image}" RW_FWID_A "$new_id"
  replace_fmap_section "${image}" RW_FWID_B "$new_id"
}

# Need to be inside the chroot to load chromeos-common.sh
assert_inside_chroot

DEFINE_integer iterations 5 "Iterations to run" x
DEFINE_string board "$FLAGS_board" "Board for which the image was built" b
DEFINE_string image "$FLAGS_image" "Location of the test image file" i
DEFINE_string firmware_ver "$FLAGS_firmware_ver" "New firmware version" f
DEFINE_string firmware_src "$FLAGS_firmware_src" \
"Location of the source firmware file" s
DEFINE_string replace_src "$FLAGS_replace_src" "Version string to replace" v

# Parse command line
FLAGS "$@" || exit 1
eval set -- "$FLAGS_ARGV"

# Convert args to paths
FLAGS_image=`eval readlink -f ${FLAGS_image}`
FLAGS_firmware_src=`eval readlink -f ${FLAGS_firmware_src}`

WORKING_DIR=/tmp/key_increment_working_folder
BIOS_WORKING_DIR="${WORKING_DIR}/bios"
IMAGE_DIR=$(dirname "${FLAGS_image}")
IMAGE_NAME=$(basename "${FLAGS_image}")
ROOT_FS_DIR="${IMAGE_DIR}/rootfs"
STATEFUL_FS_DIR="${IMAGE_DIR}/stateful"

FM_VER_PREFIX=${FLAGS_firmware_ver}
ITERATIONS=${FLAGS_iterations}

# Setup working dir
if [ -d $WORKING_DIR ]; then
  rm -rf $WORKING_DIR
fi

mkdir ${WORKING_DIR}
mkdir ${BIOS_WORKING_DIR}

info "Creating firmware binaries"
for i in $(seq 1 1 ${ITERATIONS})
do
  output="${BIOS_WORKING_DIR}/${FLAGS_board}_${FM_VER_PREFIX}.${i}.bin"
  cp "${FLAGS_firmware_src}" "${output}"
  replace_firmware_id "${output}" "${FLAGS_replace_src}.test${i}"
done

# Check we have all 5 new firmware binaries
# And verify file size should be same as the
# source firmware binary
info "Checking ${BIOS_WORKING_DIR} for binaries..."
info "Using pattern: ${FLAGS_board}_${FM_VER_PREFIX}.1.bin"
SRC_SIZE=$(stat -c%s ${FLAGS_firmware_src})
for i in $(seq 1 1 ${ITERATIONS})
do
  BIN_FILE="${BIOS_WORKING_DIR}/${FLAGS_board}_${FM_VER_PREFIX}.${i}.bin"
  if [ ! -f ${BIN_FILE} ]; then
    die_notrace "Unable to locate ${BIN_FILE} firmware binary, exiting."
  fi

  MOD_SIZE=$(stat -c%s ${BIN_FILE})
  if [ ${SRC_SIZE} -ne ${MOD_SIZE} ]; then
    die_notrace "Src (${SRC_SIZE}) and modified (${MOD_SIZE}) firmware \
file sizes are not the same, exiting."
  fi
done

# Abort on error.
IS_ABORT=true
set -e
trap on_exit EXIT

info "Copying ${FLAGS_image} to ${WORKING_DIR}"
cp $FLAGS_image $WORKING_DIR

# Pull out the shellball we want to use
"$SCRIPTS_DIR/mount_gpt_image.sh" -i "$IMAGE_NAME" -f "$WORKING_DIR" \
  -r "$ROOT_FS_DIR" -s "$STATEFUL_FS_DIR"

IMAGE_UPDATER="${ROOT_FS_DIR}/usr/sbin/chromeos-firmwareupdate"
WORKING_UPDATER="${BIOS_WORKING_DIR}/chromeos-firmwareupdate"

for i in $(seq 1 1 ${ITERATIONS})
do
  cp ${IMAGE_UPDATER} ${WORKING_UPDATER}-test$i
  chmod 755 ${WORKING_UPDATER}-test$i

  NEW_VER="${FLAGS_board}_${FM_VER_PREFIX}.${i}"
  FM_VER="Google_${NEW_VER}"
  info "Updating the firmware version to ${FM_VER}"
  sed -i \
    "/^TARGET_FWID=/c TARGET_FWID=\"${FM_VER}\"" "${WORKING_UPDATER}-test$i"
  # Clear the UNSTABLE flag.
  sed -i \
    's/^TARGET_UNSTABLE=.*/TARGET_UNSTABLE=""/' "${WORKING_UPDATER}-test$i"
  # Workaround issue crosbug.com/p/33719
  sed -i \
    's/shar -Q -q -x -m -w/shar -Q -q -x -m --no-character-count/' \
    "${WORKING_UPDATER}-test$i"

  # Resign the provided firmware binaries
  PROVIDED_BIN="${BIOS_WORKING_DIR}/${NEW_VER}.bin"
  SIGNED_BIN="${BIOS_WORKING_DIR}/${NEW_VER}_signed.bin"

  info "Resigning ${PROVIDED_BIN} to ${SIGNED_BIN}"
  cd ~/trunk/src/platform/vboot_reference/scripts/image_signing
  ./resign_firmwarefd.sh \
    "${PROVIDED_BIN}" \
    "${SIGNED_BIN}" \
    ../../tests/devkeys/firmware_data_key.vbprivk \
    ../../tests/devkeys/firmware.keyblock \
    ../../tests/devkeys/dev_firmware_data_key.vbprivk \
    ../../tests/devkeys/dev_firmware.keyblock \
    ../../tests/devkeys/kernel_subkey.vbpubk 1 0
  cd "${BIOS_WORKING_DIR}"

  mkdir work
  ./chromeos-firmwareupdate-test$i --sb_extract work/

  info "Copying new bios ${SIGNED_BIN} into ${WORKING_UPDATER}-test$i"
  sudo cp ${SIGNED_BIN} work/bios.bin
  info "Dumping keys of the firmware image:"
  vbutil_what_keys work/bios.bin
  ./chromeos-firmwareupdate-test$i --sb_repack work/
  rm -r work
done

# Get the OS version
LSB_RELEASE="${ROOT_FS_DIR}/etc/lsb-release"
CHROMEOS_VER=$(grep ^"CHROMEOS_RELEASE_VERSION" ${LSB_RELEASE} | cut -d = -f 2-)
CHROMEOS_VER_PREFIX=${CHROMEOS_VER%?}
CHROMEOS_TRACK=$(grep ^"CHROMEOS_RELEASE_TRACK" ${LSB_RELEASE} | cut -d = -f 2-)

cleanup

# Make a copy of the key directories
KEYS_DIR="${WORKING_DIR}/keys"
mkdir "${KEYS_DIR}"

cd ~/trunk/src/platform/vboot_reference
# Enable firmware update
scripts/image_signing/tag_image.sh --from="${WORKING_DIR}/${IMAGE_NAME}" \
  --update_firmware 1
cp -r tests/devkeys/* "${KEYS_DIR}"
cp scripts/keygeneration/* "${KEYS_DIR}"

# Load keygeneration helper methods
. "${KEYS_DIR}/common.sh"

# Make a directory to store the new payloads
PAYLOAD_DIR="${WORKING_DIR}/payloads"
mkdir "${PAYLOAD_DIR}"

# Create a copy of the test image that will be convert to a payload.
for i in $(seq 1 1 ${ITERATIONS})
do
  NEW_IMAGE_NAME="chromiumos-key-image-${CHROMEOS_VER_PREFIX}${i}.bin"
  cp "${WORKING_DIR}/${IMAGE_NAME}" "${WORKING_DIR}/${NEW_IMAGE_NAME}"
  "$SCRIPTS_DIR/mount_gpt_image.sh" -i "$NEW_IMAGE_NAME" -f "$WORKING_DIR" \
    -r "$ROOT_FS_DIR" -s "$STATEFUL_FS_DIR"

  info "Copying ${WORKING_UPDATER}-test${i} to ${IMAGE_UPDATER}"
  sudo cp ${WORKING_UPDATER}-test${i} ${IMAGE_UPDATER}
  NEW_CHROME_VERSION=${CHROMEOS_VER_PREFIX}${i}

  info "Updating chrome version to ${NEW_CHROME_VERSION}"
  sudo sed -i "s/${CHROMEOS_VER}/${NEW_CHROME_VERSION}/g" \
    "${ROOT_FS_DIR}/etc/lsb-release"
  sudo sed -i 's/tools/omaha.sandbox/g' "${ROOT_FS_DIR}/etc/lsb-release"

  info "Contents of the new lsb-release file"
  more "${ROOT_FS_DIR}/etc/lsb-release"
  cleanup
  cd "${KEYS_DIR}"
  if [[ ${i} == 1 ]]; then
    load_current_versions "${KEYS_DIR}"
    new_kern_ver=$(increment_version "${KEYS_DIR}" "kernel_version")
    write_updated_version_file ${CURR_FIRMKEY_VER} ${CURR_FIRM_VER} \
      ${CURR_KERNKEY_VER} ${new_kern_ver}
  elif [[ ${i} == 2 ]]; then
    "${KEYS_DIR}"/increment_kernel_data_key.sh "${KEYS_DIR}"
  elif [[ ${i} == 3  ]]; then
    "${KEYS_DIR}"/increment_kernel_subkey.sh "${KEYS_DIR}"
  elif [[ ${i} == 4  ]]; then
    "${KEYS_DIR}"/increment_firmware_data_key.sh "${KEYS_DIR}"
  elif [[ ${i} == 5  ]]; then
    load_current_versions "${KEYS_DIR}"
    new_kern_ver=$(increment_version "${KEYS_DIR}" "kernel_version")
    write_updated_version_file ${CURR_FIRMKEY_VER} ${CURR_FIRM_VER} \
      ${CURR_KERNKEY_VER} ${new_kern_ver}
    "${KEYS_DIR}"/increment_kernel_subkey_and_key.sh "${KEYS_DIR}"
    "${KEYS_DIR}"/increment_firmware_data_key.sh "${KEYS_DIR}"
  fi

  SIGNED_IMAGE_NAME="chromiumos-key-image-${CHROMEOS_VER_PREFIX}${i}_signed.bin"

  info "Resigning the image to ${SIGNED_IMAGE_NAME}..."
  cd ~/trunk/src/platform/vboot_reference
  sudo scripts/image_signing/sign_official_build.sh \
    ssd "${WORKING_DIR}/${NEW_IMAGE_NAME}" \
    "${KEYS_DIR}" \
    "${WORKING_DIR}/${SIGNED_IMAGE_NAME}" \
    "${KEYS_DIR}/key.versions"

  info "Generating payload..."
  sudo cros_generate_update_payload \
    --image="${WORKING_DIR}/${SIGNED_IMAGE_NAME}" \
    --output="${PAYLOAD_DIR}/chromeos_${CHROMEOS_VER_PREFIX}${i}\
_${FLAGS_board}_testimage-channel_full_test.bin-000${i}.signed"
done

info "All payloads are available at ${PAYLOAD_DIR}"
IS_ABORT=false

