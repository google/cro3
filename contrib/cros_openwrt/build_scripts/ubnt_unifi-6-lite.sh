#!/bin/bash
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This script preforms the necessary commands to build the current standard
# image for openwrt deployment with Ubiquiti UniFi 6 Lite test APs.

set -e

BUILD_PROFILE="ubnt_unifi-6-lite"
EXTRA_IMAGE_NAME="upreved-hostapd-v2.11-devel"
SDK_DOWNLOAD_URL="https://downloads.openwrt.org/releases/21.02.5/targets/ramips/mt7621/openwrt-sdk-21.02.5-ramips-mt7621_gcc-8.4.0_musl.Linux-x86_64.tar.xz"
IMAGE_BUILDER_DOWNLOAD_URL="https://downloads.openwrt.org/releases/21.02.5/targets/ramips/mt7621/openwrt-imagebuilder-21.02.5-ramips-mt7621.Linux-x86_64.tar.xz"
OPENWRT_SOURCE_REPO="https://github.com/openwrt/openwrt.git"
OPENWRT_SOURCE_REPO_REVISION="6198eb3e6448e9a43a32d3f46b7d0543424f455b"

SCRIPT_DIR="$(dirname "$(realpath -e "${BASH_SOURCE[0]}")")"
BUILD_DIR="${SCRIPT_DIR}/../build/${BUILD_PROFILE}"
OPENWRT_REPO_DIR="${BUILD_DIR}/openwrt"
IMAGE_BUILDER_WORKING_DIR="${BUILD_DIR}/cros_openwrt"

# Initialize build dir.
echo "Building standard OpenWRT image for profile ${BUILD_PROFILE} in ${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# Compile cros_openwrt_image_builder.
echo "Compiling cros_openwrt_image_builder"
bash "${SCRIPT_DIR}/../image_builder/build.sh"

# Clone and checkout specific openwrt repo commit needed for hostapd.
echo "Checking out official openwrt repo with commit needed for hostapd (${OPENWRT_SOURCE_REPO_REVISION})"
if [ ! -d "${OPENWRT_REPO_DIR}/.git" ]; then
  if [ -d "${OPENWRT_REPO_DIR}" ]; then
    rm -r "${OPENWRT_REPO_DIR}"
  fi
  cd "${BUILD_DIR}" && git clone "${OPENWRT_SOURCE_REPO}"
fi
cd "${OPENWRT_REPO_DIR}" && git checkout "${OPENWRT_SOURCE_REPO_REVISION}"

# Build packages once without customizations to initialize sdk.
echo "Building initial packages with standard sdk"
cros_openwrt_image_builder --working_dir "${IMAGE_BUILDER_WORKING_DIR}" \
--sdk_url "${SDK_DOWNLOAD_URL}" \
build:packages

# Customize hostapd package with repo version and rebuild packages.
echo "Customizing hostapd package source in sdk"
rm -r "${IMAGE_BUILDER_WORKING_DIR}/build/sdk/feeds/base/package/network/services/hostapd"
cp -r "${OPENWRT_REPO_DIR}/package/network/services/hostapd" "${IMAGE_BUILDER_WORKING_DIR}/build/sdk/feeds/base/package/network/services"
echo "Rebuilding packages with customized sdk"
cros_openwrt_image_builder --working_dir "${IMAGE_BUILDER_WORKING_DIR}" \
--use_existing_sdk \
build:packages

# Build final image.
echo "Building image"
cros_openwrt_image_builder --working_dir "${IMAGE_BUILDER_WORKING_DIR}" \
--image_builder_url "${IMAGE_BUILDER_DOWNLOAD_URL}" \
--image_profile "${BUILD_PROFILE}" \
--extra_image_name "${EXTRA_IMAGE_NAME}" \
build:image
