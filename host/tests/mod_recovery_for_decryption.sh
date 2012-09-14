#!/bin/bash

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This grows a signed recovery image's stateful partition to
# --statefulfs_sectors, and adds the decryption flag file. It is designed
# to be run from outside of the chroot.

SCRIPT_ROOT=/usr/lib/crosutils
. "${SCRIPT_ROOT}/common.sh" || exit 1
. /usr/lib/installer/chromeos-common.sh || exit 1
locate_gpt

assert_inside_chroot

# Default to 3GB stateful for decryption. 2097152 is 1GB.
DEFINE_integer statefulfs_sectors 6291456 \
  "number of sectors in stateful filesystem when growing"
DEFINE_string image "" \
  "source image to use (${CHROMEOS_IMAGE_NAME} if empty)"
DEFINE_string to "" \
  "emit recovery image to path/file (${CHROMEOS_RECOVERY_IMAGE_NAME} if empty)"
DEFINE_boolean verbose ${FLAGS_FALSE} \
  "log all commands to stdout" v

# Parse command line
FLAGS "$@" || exit 1
eval set -- "${FLAGS_ARGV}"

# Only now can we die on error.  shflags functions leak non-zero error codes,
# so will die prematurely if 'switch_to_strict_mode' is specified before now.
switch_to_strict_mode

if [[ ${FLAGS_verbose} -eq ${FLAGS_TRUE} ]]; then
  # Make debugging with -v easy.
  set -x
fi

#TODO: this function be moved into a common library (perhaps along
#      with the gpt functions?)
update_partition_table() {
  local src_img=$1          # source image
  local temp_state=$2       # stateful partition image
  local resized_sectors=$3  # number of sectors in resized stateful partition
  local temp_img=$4

  local kern_a_offset=$(partoffset ${src_img} 2)
  local kern_a_count=$(partsize ${src_img} 2)
  local kern_b_offset=$(partoffset ${src_img} 4)
  local kern_b_count=$(partsize ${src_img} 4)
  local rootfs_offset=$(partoffset ${src_img} 3)
  local rootfs_count=$(partsize ${src_img} 3)
  local oem_offset=$(partoffset ${src_img} 8)
  local oem_count=$(partsize ${src_img} 8)
  local esp_offset=$(partoffset ${src_img} 12)
  local esp_count=$(partsize ${src_img} 12)

  local temp_pmbr=$(mktemp -t pmbr.XXXXXX)
  dd if="${src_img}" of="${temp_pmbr}" bs=512 count=1 &>/dev/null

  trap "rm -rf '${temp_pmbr}'" EXIT
  # Set up a new partition table
  install_gpt "${temp_img}" "${rootfs_count}" "${resized_sectors}" \
    "${temp_pmbr}" "${esp_count}" false \
    $(((rootfs_count * 512)/(1024 * 1024)))

  # Copy into the partition parts of the file
  dd if="${src_img}" of="${temp_img}" conv=notrunc bs=512 \
    seek="${START_ROOTFS_A}" skip=${rootfs_offset} count=${rootfs_count}
  dd if="${temp_state}" of="${temp_img}" conv=notrunc bs=512 \
    seek="${START_STATEFUL}"
  # Copy the full kernel (i.e. with vboot sections)
  dd if="${src_img}" of="${temp_img}" conv=notrunc bs=512 \
    seek="${START_KERN_A}" skip=${kern_a_offset} count=${kern_a_count}
  dd if="${src_img}" of="${temp_img}" conv=notrunc bs=512 \
    seek="${START_KERN_B}" skip=${kern_b_offset} count=${kern_b_count}
  dd if="${src_img}" of="${temp_img}" conv=notrunc bs=512 \
    seek="${START_OEM}" skip=${oem_offset} count=${oem_count}
  dd if="${src_img}" of="${temp_img}" conv=notrunc bs=512 \
    seek="${START_ESP}" skip=${esp_offset} count=${esp_count}
}

resize_stateful() {
  # Rebuild the image with larger stateful.
  local err=0
  local large_stateful=$(mktemp)
  truncate --size $(( $FLAGS_statefulfs_sectors * 512 )) "${large_stateful}"
  trap "rm ${large_stateful}" RETURN
  /sbin/mkfs.ext4 -F -b 4096 "${large_stateful}" 1>&2

  # Create a recovery image of the right size
  # TODO(wad) Make the developer script case create a custom GPT with
  # just the kernel image and stateful.
  update_partition_table "${FLAGS_image}" "${large_stateful}" \
                         "${FLAGS_statefulfs_sectors}" "${RECOVERY_IMAGE}" 1>&2
  return $err
}

install_decryption_flag() {
  stateful_mnt=$(mktemp -d)
  offset=$(partoffset "${RECOVERY_IMAGE}" 1)
  sudo mount -o loop,offset=$(( offset * 512 )) \
    "${RECOVERY_IMAGE}" "${stateful_mnt}"
  echo -n "1" | sudo_clobber "${stateful_mnt}"/decrypt_stateful >/dev/null
  sudo umount "${stateful_mnt}"
  rmdir "${stateful_mnt}"
}

cleanup() {
  set +e
  if [[ "${FLAGS_image}" != "${RECOVERY_IMAGE}" ]]; then
    rm "${RECOVERY_IMAGE}"
  fi
}


# Main process begins here.
set -u

# No image was provided, use standard latest image path.
if [[ -z "${FLAGS_image}" ]]; then
  echo "--image required" >&2
  exit 1
fi

# Abort early if we can't find the image.
if [[ ! -f "${FLAGS_image}" ]]; then
  die_notrace "Image not found: ${FLAGS_image}"
fi

# Turn path into an absolute path.
FLAGS_image=$(readlink -f "${FLAGS_image}")
IMAGE_DIR="$(dirname "${FLAGS_image}")"
IMAGE_NAME="$(basename "${FLAGS_image}")"
RECOVERY_IMAGE="${FLAGS_to:-$IMAGE_DIR/$CHROMEOS_RECOVERY_IMAGE_NAME}"
STATEFUL_DIR="${IMAGE_DIR}/stateful_partition"

echo "Creating decryption recovery image from ${FLAGS_image}"

trap cleanup EXIT

resize_stateful

install_decryption_flag

okboat

echo "Decryption recovery image created at ${RECOVERY_IMAGE}"
print_time_elapsed
trap - EXIT
