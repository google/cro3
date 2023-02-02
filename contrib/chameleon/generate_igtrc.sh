#!/bin/bash

# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

while [[ $# -gt 0 ]]; do
  key="$1"

  case ${key} in
    -h|--help)
      echo "A script that generates the igtrc file required to run Chamelium test on IGT on a DUT."
      echo "For more info about this file, please check https://gitlab.freedesktop.org/drm/igt-gpu-tools/-/blob/master/docs/chamelium.txt#:~:text=FrameDumpPath%3D/root/"
      echo ""
      echo "Options:"
      echo "  -d, --dut_ip      IP or hostname of the DUT where the file will live and to which chamelium is connected. i.e. mydut"
      echo "  -c, --cv3_ip      IP or hostname of the chamelium itself. i.e. 192.168.0.29"
      echo "  -h, --help        Show this help message."
      exit 0
      ;;
    -d|--dut_ip)
      dut_ip="$2"
      shift # past argument
      shift # past value
      ;;
    -c|--cv3_ip)
      cv3_ip="$2"
      shift # past argument
      shift # past value
      ;;
    *)    # unknown option
      echo "Unknown option ${key}. Use -h or --help to see the available options."
      exit 1
      ;;
  esac
done

if [ -z "${dut_ip}" ] || [ -z "${cv3_ip}" ]; then
  echo "Both dut_ip and cv3_ip are required. Use -h or --help to see the available options."
  exit 1
fi

# Generate the igtrc file content
igtrc_file="[Common]
# The path to dump frames that fail comparison checks
FrameDumpPath=/tmp

[DUT]
SuspendResumeDelay=15

# IP address of the Chamelium
# The ONLY mandatory field
[Chamelium]
URL=http://${cv3_ip}:9992

# The ID of the chamelium port <> DUT port mapping
# DUT port can be found and should match |modetest -c|
# Replace the IDs below by yours
# It is an optional field. When no set, Chamelium will perform autodiscovery.
#[Chamelium:DP-4]
#ChameliumPortID=0
"

# Check if dut_ip is in IP format
if [[ ${dut_ip} =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  target_dut_ip="root@${dut_ip}"
else
  target_dut_ip="${dut_ip}"
fi


# Write the igtrc file to the remote device
if ssh "${target_dut_ip}" "echo '${igtrc_file}' > ~/.igtrc4"; then
  echo "igtrc file successfully written to the remote device at ${dut_ip}."
else
  echo "Error: Failed to write igtrc file to the remote device. Make sure rootfs verification has been removed by running |sudo /usr/share/vboot/bin/make_dev_ssd.sh --remove_rootfs_verification|"
fi
