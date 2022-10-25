#!/bin/bash
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This is a workaround for running "make image" with the OpenWrt image builder
# with its "parameters". These cannot be cleanly set with normal Command call in
# go since they set environment variables in a non-standard way.

set -e

BUILDER_DIR="$1"
PROFILE="$2"
PACKAGES="$3"
FILES="$4"
EXTRA_IMAGE_NAME="$5"
DISABLED_SERVICES="$6"

cd "${BUILDER_DIR}" && umask 022 && make image \
PROFILE="${PROFILE}" \
PACKAGES="${PACKAGES}" \
FILES="${FILES}" \
EXTRA_IMAGE_NAME="${EXTRA_IMAGE_NAME}" \
DISABLED_SERVICES="${DISABLED_SERVICES}"
