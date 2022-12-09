#!/bin/bash
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Script run from a DUT to report broad summary of characteristics and state
# Example usage: ssh $DUT <device_summary.sh

keyval() {
  # Pads keys with whitespace to align output
  KEY_FIELD_LENGTH=20
  printf "%-${KEY_FIELD_LENGTH}s: %s\n" "$1" "$2"
}

usage-error() {
  2>&1 echo "This device doesn't appear to be a ChromeOS DUT."
  2>&1 echo "Run this script on the DUT, not on the host."
  2>&1 echo "To execute remotely, try 'ssh \$DUT <${0}'"
  exit 1
}

# Detect host machine inside chroot
if [ -f /etc/cros_chroot_version ]; then
  usage-error
fi

HWID="$(crossystem hwid)"
keyval "HWID" "${HWID}"

SERIAL="$(vpd -g serial_number)"
keyval "Serial" "${SERIAL}"

echo
echo "#Software"

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

BROWSER="$(/opt/google/chrome/chrome --version)"
keyval "Chrome Browser" "${BROWSER}"

KERNEL="$(uname -r)"
keyval "Kernel" "${KERNEL}"

FW_ACTIVE="$(crossystem fwid)"
keyval "Firmware (active)" "${FW_ACTIVE}"
FW_RO="$(crossystem ro_fwid)"
keyval "Firmware (read-only)" "${FW_RO}"

EC="$(ectool version 2>&1 | grep 'Build info' | awk '{ print $3 }')"
keyval "EC" "${EC}"

# Features that might vary by SKU

echo
echo "#Hardware characteristics"

SKU= # appease shellcheck
eval "$(crosid)" # sets SKU
keyval "Firmware SKU ID" "${SKU}"

CPU_MODEL="$(grep "^model name" /proc/cpuinfo | head -n1)"
keyval "CPU" "${CPU_MODEL:13}"

CORES="$(nproc --all)"
keyval "CPU cores" "${CORES}"

MEM_KB="$(grep '^MemTotal:' /proc/meminfo  | awk '{ print $2 }')"
MEM_CHANNELS="$(dmidecode -t memory | grep Locator | grep -c Channel)"
keyval "Memory" "$((MEM_KB / 1024))M, ${MEM_CHANNELS} channels"

# Heuristic - storage size based on largest lsblk output
STORAGE="$(lsblk -x SIZE -o SIZE | tail -n1)"
keyval "Storage" "${STORAGE}"

# Drivers
echo
echo "#Drivers"

MEDIA="$(vainfo 2>/dev/null | grep 'Driver version' \
  | awk -F : '{ print $3 }' | sed 's/^\s//')"
keyval "Media" "${MEDIA}"

LIBVA="$(vainfo 2>/dev/null | grep 'vainfo: VA-API version' \
  | awk -F : '{ print $3 }' | sed 's/^\s//')"
keyval "VA API" "${LIBVA}"

MESA="$(wflinfo -p null -a gles2 2>/dev/null | grep -E -o 'Mesa (\.?[[:digit:]]+)*')"
keyval "Mesa" "${MESA}"
