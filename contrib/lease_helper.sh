#!/bin/bash
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
# This helper script uses crosfleet to lease a dut and then opens ssh tunnels
# to both the dut and the servo which will automatically shut down after the lease
# time is up.  Can also be used for wificell duts where it will setup tunnels to
# the Wi-Fi AP/PCAP devices see go/htl-customers for more info on wificell test
# setup
# example run:
# (outside) ./scripts/lease_helper.sh -board dedede -minutes 30
# (inside) test_that localhost:2222 TEST
# will setup ssh tunnel to DUT on port 2222 and servo on port 9999
# example run for wificell DUT
# (outside) ./scripts/lease_helper.sh -wifi -dim label-cts_cpu:CTS_CPU_X86 -minutes 300
# (inside) tast run -var=router=localhost:2223 -var=pcap=localhost:2224 localhost:2222 wifi.ChannelScanDwellTime

RED='\033[38;5;9m'
BLUE='\033[38;5;12m'
NC='\033[0m' # No Color

# set these to make shellcheck happy lease_dut will override with values from
# crosfleet lease
DUT_HOSTNAME=
SERVO_HOSTNAME=
SERVO_PORT=
SERVO_SERIAL=
BOARD=

_echo_color() {
  printf "${1}%s${NC}\n" "${2}"
}

_echo_error() {
  _echo_color >&2 "${RED}" "$*" 1
}

lease_dut() {
  _echo_color "${BLUE}" "Leasing DUT..."
  TEMP_FILE="$(mktemp)"
  if ! crosfleet dut lease "$@" > "${TEMP_FILE}" 2>&1 ; then
    _echo_error "Error leasing DUT"
    cat "${TEMP_FILE}"
    rm "${TEMP_FILE}"
    exit 1
  fi

  grep "[A-Z_]*=.*" "${TEMP_FILE}" | sed 's/^/export /' > "${HOME}/dutenv.sh"
  # shellcheck disable=SC1091
  . "${HOME}/dutenv.sh"
  rm "${TEMP_FILE}"
  cat "${HOME}/dutenv.sh"
}

start_tunnels() {
  # start tunnel to dut with ssh watcher and start tunnel to servo along with servod
  SSHWATCHER_ARGS=( "${DUT_HOSTNAME}" "2222" "${SERVO_HOSTNAME}" "9999")
  if [ "$1" -eq "1" ]; then
    # if WIFI DUT then setup tunnels to router/pcap Gales
    SSHWATCHER_ARGS+=( "${DUT_HOSTNAME}-router" "2223" "${DUT_HOSTNAME}-pcap" "2224" )
  fi
  go run "${SSHWATCHER_PATH}" "${SSHWATCHER_ARGS[@]}" >/dev/null &
  ssh -L "${SERVO_HOSTNAME}" servod --port "${SERVO_PORT}" --serialname "${SERVO_SERIAL}" -b "${BOARD}" > /dev/null &
  sleep 10
  _echo_color "${BLUE}" "dut on port 2222, servo on port 9999"
}

kill_tunnels() {
  # shut down tunnels after lease time or ctrl-c
  _echo_color "${BLUE}" "Stopping all ssh tunnels"
  # shellcheck disable=SC2046
  kill $(jobs -p) 2 > /dev/null 2>&1
  pgrep -f "[s]sh.*${DUT_HOSTNAME}" | xargs kill 2>/dev/null
  pgrep -f "[s]sh.*${SERVO_HOSTNAME}" | xargs kill 2>/dev/null
}

trap ctrl_c INT

ctrl_c() {
  _echo_color "${BLUE}" "Got ctl-c shutting down"
}

check_setup() {
  if ! command -v gcert >/dev/null 2>&1 || ! command -v corp-ssh-helper >/dev/null 2>&1; then
    _echo_error "Error: gcert or corp-ssh-helper is not installed.  This script"
    _echo_error "        only works from corp enrolled machines which should have both."
    exit 1
  fi

  if ! command -v crosfleet >/dev/null 2>&1; then
    _echo_error "Error: crosfleet is not installed.  Please install it."
    echo "https://g3doc.corp.google.com/company/teams/chrome/ops/chromeos/chromeos-infra/test_platform/internal/tools/crosfleet.md?cl=head"
    exit 1
  fi

  if [[ ! -f ~/.ssh/testing_rsa ]]; then
    _echo_error "Error: Please add the testing_rsa key to your .ssh folder."
    echo "https://g3doc.corp.google.com/company/teams/chrome/ops/fleet/software/access_lab_duts.md?cl=head"
    exit 1
  fi

  if [ "${CROS_REPO_DIR}" = "" ]; then
    CROS_REPO_DIR="${HOME}/chromiumos"
  fi
  SSHWATCHER_PATH="${CROS_REPO_DIR}/src/platform/dev/contrib/sshwatcher/sshwatcher.go"
  if [[ ! -f "${SSHWATCHER_PATH}" ]]; then
    _echo_error "Error could not find ${SSHWATCHER_PATH}"
    _echo_error "If your cros repo checkout is not at ~/chromiumos please set CROS_REPO_DIR"
    exit 1
  fi

  echo "Checking for the SSH certificate."
  if ! gcertstatus; then
    _echo_error "Error: Please run gcert to get a new SSH certificate."
    # exit 1
  fi
}

main() {
  check_setup
  WIFI=0
  CROSFLEET_ARGS=()
  MINUTES=60
  # parse command line args passing on unparsed options to crosfleet along with
  # extra args that may be generated for certain scrip command line args
  while [[ $# -gt 0 ]]; do
    case $1 in
      -wifi|--wifi)
        WIFI=1
        CROSFLEET_ARGS+=( "-dim" "label-pool=wificell" )
        shift
        ;;
      -minutes|--minutes)
        MINUTES="$2"
        CROSFLEET_ARGS+=( "$1" "$2" )
        shift # past argument
        shift # past value
        ;;
      *)
        CROSFLEET_ARGS+=( "$1" )
        shift # past argument
        ;;
    esac
  done
  lease_dut "${CROSFLEET_ARGS[@]}"
  start_tunnels "${WIFI}"

  _echo_color "${BLUE}" "Waiting for ${MINUTES} minute lease to expire"
  sleep "${MINUTES}m"
  kill_tunnels
}

main "$@"
