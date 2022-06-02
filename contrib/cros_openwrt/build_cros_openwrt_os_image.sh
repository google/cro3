#!/bin/bash
# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Uses the OpenWrt image builder to create an image that matches the provided
# standard image configuration plus changes to the image that allow the features
# necessary for testing with OpenWrt.
#
# OpenWrt Image Builder docs: https://openwrt.org/docs/guide-user/additional-software/imagebuilder

set -e

SCRIPT_DIR="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"

function print_usage {
  cat << EOF
Usage: $0 <image_builder_archive_path_or_url> <build_profile>

You can also run without a build profile to see which profiles are available
with the provided image builder.

For more documentation, see the README at
"${SCRIPT_DIR}/README.md".
EOF
}

if [ "$#" == 0 ] || [ "$1" == "-h" ] || [ "$1" == "help" ] \
|| [ "$1" == "--help" ]; then
  print_usage
  exit 0
fi

IMAGE_BUILDER_ARCHIVE_PATH="$1"
BUILD_PROFILE="$2"
CROS_IMAGE_VERSION=0.1.3

if [ "${IMAGE_BUILDER_ARCHIVE_PATH}" == "" ]; then
  echo "Error: missing image_builder_archive_path_or_url argument"
  print_usage
  exit 1
fi
CHROMIUMOS_DIR_PATH="$(realpath "${SCRIPT_DIR}/../../../../..")"

# Prepare build dir.
BASE_TMP_DIR="/tmp/openwrt_img_building"
if [ ! -d "${BASE_TMP_DIR}" ]; then
  mkdir -p "${BASE_TMP_DIR}"
fi

# Unpack image builder, downloading the archive if it is a url
BUILDERS_TMP_DIR="${BASE_TMP_DIR}/builders"
BUILDER_ARCHIVE_FILENAME="${IMAGE_BUILDER_ARCHIVE_PATH##*/}"
BUILDER_DIR="${BUILDERS_TMP_DIR}/${BUILDER_ARCHIVE_FILENAME:0:-7}"
echo "IMAGE_BUILDER_ARCHIVE_PATH=${IMAGE_BUILDER_ARCHIVE_PATH}"
echo "BUILDER_ARCHIVE_FILENAME=${BUILDER_ARCHIVE_FILENAME}"
echo "BUILDER_DIR=${BUILDER_DIR}"
if [ ! -d "${BUILDER_DIR}" ]; then
  mkdir -p "${BUILDER_DIR}"
  DOWNLOADED_ARCHIVE=0
  if [[ "${IMAGE_BUILDER_ARCHIVE_PATH}" =~ ^http.* ]]; then
    ARCHIVE_URL="${IMAGE_BUILDER_ARCHIVE_PATH}"
    IMAGE_BUILDER_ARCHIVE_PATH="${BUILDERS_TMP_DIR}/${BUILDER_ARCHIVE_FILENAME}"
    if [ ! -f "${IMAGE_BUILDER_ARCHIVE_PATH}" ]; then
      echo "Downloading image builder archive from '${ARCHIVE_URL}' to '${IMAGE_BUILDER_ARCHIVE_PATH}'..."
      wget "${ARCHIVE_URL}" -O "${IMAGE_BUILDER_ARCHIVE_PATH}"
      DOWNLOADED_ARCHIVE=1
    fi
  fi
  echo "Extracting image builder from archive '${IMAGE_BUILDER_ARCHIVE_PATH}'..."
  tar -Jxf "${IMAGE_BUILDER_ARCHIVE_PATH}" -C "${BUILDER_DIR}"
  NESTED_BUILDER_DIR="${BUILDER_DIR}/$(ls "${BUILDER_DIR}")"
  echo "Moving files from '${NESTED_BUILDER_DIR}' to '${BUILDER_DIR}'"
  find "${NESTED_BUILDER_DIR}" -mindepth 1 -maxdepth 1 -exec mv '{}' "${BUILDER_DIR}" \;
  rmdir "${NESTED_BUILDER_DIR}"
  echo "Successfully unpacked builder to '${BUILDER_DIR}'"
  if [ "${DOWNLOADED_ARCHIVE}" -eq 1 ]; then
    rm "${IMAGE_BUILDER_ARCHIVE_PATH}"
    echo "Deleted downloaded archive '${IMAGE_BUILDER_ARCHIVE_PATH}'"
  fi
fi
echo "Using image builder directory '${BUILDER_DIR}'"

if [ "${BUILD_PROFILE}" == "" ]; then
  echo "Error: No build profile specified"
  echo "Available build profiles with this builder:"
  cd "${BUILDER_DIR}" && make info
  echo "Please select a build profile and re-run the script with the profile name as the second argument"
  echo "Usage: $0 $1 <build_profile>"
  exit 1
fi

# Collect files to copy to build.
FILES_DIR="${BASE_TMP_DIR}/included_image_files"
if [ -d "${FILES_DIR}" ]; then
  rm -rf "${FILES_DIR}"
fi
mkdir "${FILES_DIR}"
cp -R "${SCRIPT_DIR}"/included_image_files/* "${FILES_DIR}"

# Allow the shared test key to be used for ssh access to router.
PATH_TO_CROS_PUB_KEY="${CHROMIUMOS_DIR_PATH}/chromeos-admin/puppet/modules/profiles/files/user-common/ssh/testing_rsa.pub"
mkdir -p "${FILES_DIR}/etc/dropbear"
cp "${PATH_TO_CROS_PUB_KEY}" "${FILES_DIR}/etc/dropbear/authorized_keys"


# Customize packages.
PACKAGES=(
  # Veth support.
  "kmod-veth"

  # Full hostapd support using OpenSSL.
  "wpad-openssl"
  "libopenssl-conf"
  "-wpad-basic"
  "-wpad-basic-openssl"
  "-wpad-basic-wolfssl"
  "-wpad-mesh-openssl"
  "-wpad-mesh-wolfssl"
  "-wpad-mini"
  "-wpad-wolfssl"

  # Packet capturing support.
  "tcpdump"

  # Add the hostapd_cli utility.
  "hostapd-utils"

  # Add pkill utility
  "procps-ng-pkill"
)
PACKAGES_STR=$(IFS=' '; echo -n "${PACKAGES[@]}")

# Disable unused services.
DISABLED_SERVICES=(
  "wpad" # Hostapd process is managed directly by test harness, not OpenWrt.
  "dnsmasq" # dnsmasq processes is managed directly by test harness.
)
DISABLED_SERVICES_STR=$(IFS=' '; echo -n "${DISABLED_SERVICES[@]}")

# Add an image build summary to its files.
CROS_FILES_DIR="${FILES_DIR}/etc/cros"
mkdir -p "${CROS_FILES_DIR}"
BUILD_INFO_FILE_PATH="${CROS_FILES_DIR}/build_info"
cat > "${BUILD_INFO_FILE_PATH}" << EOF
CROS_IMAGE_VERSION="${CROS_IMAGE_VERSION}"
IMAGE_CREATED_AT="$(date --iso-8601=seconds)"
IMAGE_BUILDER_ARCHIVE_PATH="${IMAGE_BUILDER_ARCHIVE_PATH}"
BUILD_PROFILE="${BUILD_PROFILE}"
PACKAGES="${PACKAGES_STR}"
DISABLED_SERVICES="${DISABLED_SERVICES_STR}"
EOF
cat >> "${BUILD_INFO_FILE_PATH}" << EOF
CUSTOM_IMAGE_FILES=$(cd "${FILES_DIR}" && find . -mindepth 1 -type f -printf "\"%p\" ")
EOF

# Build image.
BIN_DIR="${BASE_TMP_DIR}/bin"
EXTRA_IMAGE_NAME="cros-${CROS_IMAGE_VERSION}"
echo "Building image..."

cd "${BUILDER_DIR}" && umask 022 && make image \
PROFILE="${BUILD_PROFILE}" \
PACKAGES="${PACKAGES_STR}" \
FILES="${FILES_DIR}" \
BIN_DIR="${BIN_DIR}" \
EXTRA_IMAGE_NAME="${EXTRA_IMAGE_NAME}" \
DISABLED_SERVICES="${DISABLED_SERVICES_STR}"

echo "Successfully built image"
echo ""
echo "Build Info (Saved to image at '/etc/cros/build_info'):"
cat "${BUILD_INFO_FILE_PATH}"
echo ""
echo "Available Images:"
find "${BIN_DIR}" -name "*.bin"
