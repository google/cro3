#!/bin/sh /etc/rc.common
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Configure this init script to run after all other scripts by setting the
# last possible order (99) and having the script filename start with "z". Other
# init scripts exist with order 99, so the "z" forces this script to also go
# after those as order is determined by ascii sort.
START=99
STOP=99

CROS_TMP_DIR="/tmp/cros"
CROS_TMP_STATUS_DIR="${CROS_TMP_DIR}/status"
CROS_TMP_TEST_DIR="${CROS_TMP_DIR}/test"
CROS_STATUS_READY_FILE="${CROS_TMP_STATUS_DIR}/ready"

start() {
    if [ -d "${CROS_TMP_DIR}" ]; then
        rm -rf "${CROS_TMP_DIR}"
    fi
    mkdir "${CROS_TMP_DIR}"
    mkdir "${CROS_TMP_STATUS_DIR}"
    mkdir "${CROS_TMP_TEST_DIR}"
    date > "${CROS_STATUS_READY_FILE}"
}

stop() {
    rm -rf "${CROS_TMP_DIR}"
}
