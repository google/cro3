#!/bin/bash
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Script run from a DUT to report broad summary of characteristics and state
# Example usage: ssh $DUT <device_summary.sh

# TODO(b/242093024) combine with get_device_info.sh

function keyval {
  # Pads keys with whitespace to align output
  KEY_FIELD_LENGTH=20
  printf "%-${KEY_FIELD_LENGTH}s: %s\n" "$1" "$2"
}

function usage-error {
  2>&1 echo "This device doesn't appear to be a ChromeOS DUT."
  2>&1 echo "Run this script on the DUT, not on the host."
  2>&1 echo "To execute remotely, try 'ssh \$DUT <${0}'"
  exit 1
}

# Detect host machine inside chroot
if [ -f /etc/cros_chroot_version ]; then
  usage-error
fi

BOARD="$(grep CHROMEOS_RELEASE_BOARD </etc/lsb-release)"
# Detect host machine outside chroot
if [ -z "${BOARD}" ]; then
  usage-error
fi
keyval "Board" "${BOARD:23}"

MODEL="$(cros_config / name)"
keyval "Model" "${MODEL}"

OS="$(grep CHROMEOS_RELEASE_VERSION </etc/lsb-release)"
MILESTONE="$(grep CHROMEOS_RELEASE_CHROME_MILESTONE </etc/lsb-release)"
keyval "ChromeOS" "${OS:25} (M${MILESTONE:34})"

KERNEL="$(uname -r)"
keyval "Kernel" "${KERNEL}"

FW_ACTIVE="$(crossystem fwid)"
keyval "Firmware (active)" "${FW_ACTIVE}"
FW_RO="$(crossystem ro_fwid)"
keyval "Firmware (read-only)" "${FW_RO}"

HWID="$(crossystem hwid)"
keyval "HWID" "${HWID}"

SERIAL="$(vpd -g serial_number)"
keyval "Serial" "${SERIAL}"

SKU= # appease shellcheck
eval "$(crosid)" # sets SKU
keyval "Firmware SKU ID" "${SKU}"

# Features that might vary by SKU

CPU_MODEL="$(grep "^model name" /proc/cpuinfo | head -n1)"
keyval "CPU" "${CPU_MODEL:13}"

MEM_KB="$(grep '^MemTotal:' /proc/meminfo  | awk '{ print $2 }')"
keyval "Memory" "$((MEM_KB / 1024))M"
