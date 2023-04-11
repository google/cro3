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
CROS_BOOT_LOG_DIR="/root/cros_boot_log"
CROS_BOOT_STATE_FILE="${CROS_BOOT_LOG_DIR}/boot_state_log.csv"
CROS_BOOT_STATE_PREV_FILE="${CROS_BOOT_LOG_DIR}/boot_state_log.prev.csv"
LAST_BOOT_ID_FILE="${CROS_BOOT_LOG_DIR}/last_boot_id.txt"
MAX_RECORDED_BOOTS=20
MAX_BOOT_STATE_ROWS=500

prepare_tmp_test_dir() {
  if [ -d "${CROS_TMP_DIR}" ]; then
    rm -rf "${CROS_TMP_DIR}"
  fi
  mkdir "${CROS_TMP_DIR}"
  mkdir "${CROS_TMP_STATUS_DIR}"
  mkdir "${CROS_TMP_TEST_DIR}"
  date -u -Is > "${CROS_STATUS_READY_FILE}"
}

record_and_verify_boot() {
  # Prepare log dir.
  if [ ! -d "${CROS_BOOT_LOG_DIR}" ]; then
    mkdir -p "${CROS_BOOT_LOG_DIR}"
  fi

  # Get the last boot ID (defaulting to 0 if it does not exist or is NAN).
  LAST_BOOT_ID=0
  if [ -f "${LAST_BOOT_ID_FILE}" ]; then
    LAST_BOOT_ID=$(cat "${LAST_BOOT_ID_FILE}")
    if ! [ "${LAST_BOOT_ID}" -eq "${LAST_BOOT_ID}" ] 2>/dev/null; then
      LAST_BOOT_ID=0
    fi
  fi

  # Calculate next boot ID.
  BOOT_ID=$((LAST_BOOT_ID+1))
  if [ "${BOOT_ID}" -gt "${MAX_RECORDED_BOOTS}" ]; then
    BOOT_ID=1
  fi
  BOOT_NAME="boot_$(printf "%02d" "${BOOT_ID}")"
  echo -n "${BOOT_ID}" > "${LAST_BOOT_ID_FILE}"

  # Initialize new record dir.
  RECORD_DIR="${CROS_BOOT_LOG_DIR}/${BOOT_NAME}"
  if [ -d "${RECORD_DIR}" ]; then
    # Max boot records reached, replacing old boot dir.
    rm -r "${RECORD_DIR}"
  fi
  mkdir -p "${RECORD_DIR}"

  # Wait for links to all be up or it times out.
  BOOT_CHECK_RESULT_FILE="${RECORD_DIR}/boot_check_result.csv"
  BOOT_CHECK_RESULT_HEADER="PING_GOOGLE_DNS_ERROR,LINK_STATE_ETH0,LINK_STATE_LAN,LINK_STATE_BR_LAN"
  echo "${BOOT_CHECK_RESULT_HEADER}" > "${BOOT_CHECK_RESULT_FILE}"
  SUCCESS_RESULT="0,up,up,up"
  BOOT_CHECK_RESULT=""
  UPTIME_WAIT_SECONDS=30
  while [ "${BOOT_CHECK_RESULT}" != "${SUCCESS_RESULT}" ] && [ "${UPTIME_WAIT_SECONDS}" -gt 0 ]; do
    if [ "${BOOT_CHECK_RESULT}" != "" ]; then
      sleep 1
    fi
    ping -w 1 -c 1 8.8.8.8 > /dev/null
    PING_GOOGLE_DNS_ERROR=$?
    LINK_STATE_ETH0=$(cat "/sys/class/net/eth0/operstate")
    LINK_STATE_LAN=$(cat "/sys/class/net/lan/operstate")
    LINK_STATE_BR_LAN=$(cat "/sys/class/net/br-lan/operstate")
    BOOT_CHECK_RESULT="${PING_GOOGLE_DNS_ERROR},${LINK_STATE_ETH0},${LINK_STATE_LAN},${LINK_STATE_BR_LAN}"
    echo "$(date -u -Is) : ${BOOT_CHECK_RESULT}" >> "${BOOT_CHECK_RESULT_FILE}"
    UPTIME_WAIT_SECONDS=$((UPTIME_WAIT_SECONDS-1))
  done

  # Record last network state.
  ip link show > "${RECORD_DIR}/ip_link_show.txt"
  ifconfig > "${RECORD_DIR}/ifconfig.txt"
  free -m > "${RECORD_DIR}/free_mem.txt"
  netstat -plunt > "${RECORD_DIR}/netstat_plunt.txt"

  # Prepare boot state log.
  BOOT_STATE_HEADER="BOOT_NAME,BOOT_CHECK_RESULT,${BOOT_CHECK_RESULT_HEADER}"
  LAST_CHECK_WAS_FAILURE=0
  if [ ! -f "${CROS_BOOT_STATE_FILE}" ]; then
    # New log.
    echo "${BOOT_STATE_HEADER}" > "${CROS_BOOT_STATE_FILE}"
  else
    # Existing log, make sure it's not full.
    LAST_CHECK_WAS_FAILURE=$(tail -1 "${CROS_BOOT_STATE_FILE}" | grep -q "FAILURE")
    BOOT_STATE_DATA_ROWS=$(($(wc -l < "${CROS_BOOT_STATE_FILE}")-1))
    if [ "${BOOT_STATE_DATA_ROWS}" -ge "${MAX_BOOT_STATE_ROWS}" ]; then
      # Full log, archive log and create a fresh log.
      if [ -f "${CROS_BOOT_STATE_PREV_FILE}" ]; then
        # Remove last archive, we only keep one at a time.
        rm "${CROS_BOOT_STATE_PREV_FILE}"
      fi
      mv "${CROS_BOOT_STATE_FILE}" "${CROS_BOOT_STATE_PREV_FILE}"
      echo "${BOOT_STATE_HEADER}" > "${CROS_BOOT_STATE_FILE}"
    fi
  fi

  # Evaluate and record final boot check.
  if [ "${BOOT_CHECK_RESULT}" != "${SUCCESS_RESULT}" ]; then
    # Boot check failed. Reboot if not already rebooted due to a previous failure.
    echo "${BOOT_NAME},FAILURE,${BOOT_CHECK_RESULT}" >> "${CROS_BOOT_STATE_FILE}"
    if [ "${LAST_CHECK_WAS_FAILURE}" -ne 0 ]; then
      reboot
    fi
  else
    echo "${BOOT_NAME},SUCCESS,${BOOT_CHECK_RESULT}" >> "${CROS_BOOT_STATE_FILE}"
  fi
}

start() {
  record_and_verify_boot
  prepare_tmp_test_dir
}

stop() {
    rm -rf "${CROS_TMP_DIR}"
}
