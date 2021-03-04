#!/bin/bash
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Loads script libraries.
CONTRIB_DIR=$(dirname "$(readlink -f "$0")")
. "${CONTRIB_DIR}/common.sh" || exit 1

assert_inside_chroot

# Load remote library
REMOTE_LIB="/home/$USER/trunk/src/scripts"
. "${REMOTE_LIB}/remote_access.sh" || exit 1

cf_help="Removes the headers from the output."

DEFINE_boolean debug $FLAGS_FALSE "Enables debug logging."
DEFINE_boolean copy_friendly $FLAGS_FALSE "${cf_help}"

# Parse command line.
FLAGS "$@" || exit 1
eval set -- "${FLAGS_ARGV}"

cleanup() {
    logd "Activated trap card. Exiting..."
    cleanup_remote_access
    rm -rf "${TMP}"
}

# Removing leading and trailing whitespace.
remove_whitespace() {
    space_match=${1##*[! ]}             # Match prefixed spaces.
    trimmed=${1%"$space_match"}         # Remove prefixed spaces.
    space_match=${trimmed%%[! ]*}       # Match postfixed spaces.
    trimmed=${trimmed#"$space_match"}   # Remove postfixed spaces.
    printf "$trimmed"
}

# Generic debug logger.
logd() {
    if [ ${FLAGS_debug} = ${FLAGS_TRUE} ]; then
        printf "DEBUG: $1\n"
    fi
}

# Debug 'start' function for a section type.
log_status_start() {
    if [ ${FLAGS_debug} = ${FLAGS_TRUE} ]; then
        printf "DEBUG: Getting ${1} information..."
    fi
}

# Debug 'end' function for a section type.
log_status_end() {
    if [ ${FLAGS_debug} = ${FLAGS_TRUE} ]; then
        if [ ! -z "${1}" ]; then
            printf "Complete!\n"
        else
            printf "Failed!\n"
        fi
    fi
}

# Uses remote_sh to pass a command, but acts like a try/fail
# condition, returning an empty string upon failure.
try_remote_command() {
    remote_sh "${1} || printf ''"
}

main() {
    trap cleanup EXIT

    TMP=$(mktemp -d /tmp/get_dut_info.XXXX)

    remote_access_init

    log_status_start "Board Name"
    try_remote_command "grep CHROMEOS_RELEASE_BOARD /etc/lsb-release"
    if [ ! -z "${REMOTE_OUT}" ]; then
        BOARD=$(printf "${REMOTE_OUT}" | cut -d '=' -f 2)
    fi
    log_status_end "${BOARD}"

    log_status_start "OS Version"
    command="awk -F = '\$1 ~ /CHROMEOS_RELEASE_DESCRIPTION/ \
{print \$2}' /etc/lsb-release"
    try_remote_command "${command}"
    OS="${REMOTE_OUT}"
    log_status_end "${OS}"

    log_status_start "Chrome Browser"
    try_remote_command "/opt/google/chrome/chrome --version"
    CHROME="${REMOTE_OUT}"
    log_status_end "${CHROME}"

    log_status_start "Firmware"
    try_remote_command "crossystem fwid"
    FW="${REMOTE_OUT}"
    if [[ -z "$FW" ]]; then
        command="dmidecode | sed -n '/BIOS Information/,/Handle/p' \
| grep \"Version\""
        try_remote_command "${command}"
        ver="${REMOTE_OUT}"
        ver=$(remove_whitespace "$ver")
        FW=$( printf "${ver}" | awk '{print $2}' )
    fi
    log_status_end "${FW}"

    log_status_start "EC"
    try_remote_command "(ectool version 2>&1 | grep 'Build info')"
    EC=$(printf "${REMOTE_OUT}" | awk '{ print $3 }')
    log_status_end "${EC}"

    log_status_start "CPU"
    command="awk -F : '\$1 ~ /model name/ {print \$2}' \
/proc/cpuinfo | head -1"
    try_remote_command "${command}"
    CPU="${REMOTE_OUT}"
    CPU=$(remove_whitespace "$CPU")
    log_status_end "${CPU}"

    log_status_start "Kernel"
    try_remote_command "uname -smr"
    KERNEL="${REMOTE_OUT}"
    log_status_end "${KERNEL}"

    log_status_start "Memory (Physical)"
    try_remote_command "cat /proc/meminfo | grep MemTotal"
    MEM="${REMOTE_OUT}"
    MEM=$(printf "$MEM" | awk '{print $2}')
    if [[ ! -z $MEM ]] && [[ $MEM == [0-9]* ]] && [ $MEM -ne 0 ]; then
        # Conversion from system kB to manufactuer GB
        MEM=$(($MEM * 1024 / 1000000000 ))
    else
        MEM=""
    fi
    log_status_end "${MEM}"

    log_status_start "Memory Channels"
    try_remote_command "dmidecode -t memory | grep Channel | wc -l"
    MEM_CHANNELS="${REMOTE_OUT}"
    log_status_end "${MEM_CHANNELS}"

    log_status_start "Storage"
    command="lsblk -o PKNAME,MOUNTPOINT \
| grep \"/mnt/stateful_partition$\""
    try_remote_command "${command}"
    storage_type=$(printf "${REMOTE_OUT}" | awk '{print $1}')
    try_remote_command "lsblk -b --nodeps | grep -w $storage_type"
    STORAGE=$(printf "${REMOTE_OUT}" | awk '{print $4}')
    if [[ ! -z "$STORAGE" ]]; then
        # Conversion from system bytes to manufactuer GB
        STORAGE=$(($STORAGE * 1024 / 1000000000000 ))
    fi
    log_status_end "${STORAGE}"

    log_status_start "Core Number"
    try_remote_command "nproc --all"
    CORES="${REMOTE_OUT}"
    log_status_end "${CORES}"

    log_status_start "Media"
    try_remote_command "vainfo 2>/dev/null | grep 'Driver version'"
    MEDIA=$(printf "${REMOTE_OUT}" | awk -F : '{print $3}'| sed 's/^\s//')
    log_status_end "${MEDIA}"

    log_status_start "Libva"
    try_remote_command "vainfo 2>/dev/null | grep 'vainfo: VA-API version'"
    LIBVA=$(printf "${REMOTE_OUT}" | awk -F : '{print $3}'| sed 's/^\s//')
    log_status_end "${LIBVA}"

    log_status_start "Mesa"
    try_remote_command "wflinfo -p null -a gles2 2>/dev/null | egrep -o '(Mesa [[:digit:]].*?)\s'"
    MESA="${REMOTE_OUT}"
    log_status_end "${MESA}"

    logd "Information gathering complete!"

    mem_message="${MEM:-(unknown) }GB (physical), \
${MEM_CHANNELS:-(unknown)} channels"
    if [ "${FLAGS_copy_friendly}" = "${FLAGS_TRUE}" ]; then
        cat <<EOF
${BOARD:-(unknown)}
${OS:-(unknown)}
${CHROME:-(unknown)}
${FW:-(unknown)}
${EC:-(unknown)}
${CPU:-(unknown)} (${CORES:-(unknown)} cores)
${KERNEL:-(unknown)}
${mem_message}
${STORAGE:-(unknown) }GB
${MEDIA:-(unknown)}
${LIBVA:-(unknown)}
${MESA:-(unknown)}
EOF

    else
        cat <<EOF
  Board: ${BOARD:-(unknown)}
     OS: ${OS:-(unknown)}
 Chrome: ${CHROME:-(unknown)}
     FW: ${FW:-(unknown)}
     EC: ${EC:-(unknown)}
    CPU: ${CPU:-(unknown)} (${CORES:-(unknown)} cores)
 Kernel: ${KERNEL:-(unknown)}
    Mem: ${mem_message}
Storage: ${STORAGE:-(unknown) }GB
  Media: ${MEDIA:-(unknown)}
  Libva: ${LIBVA:-(unknown)}
   Mesa: ${MESA:-(unknown)}
EOF
    fi
}

main "$@"
