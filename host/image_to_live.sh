#!/bin/bash

# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Script to update an image onto a live running ChromiumOS instance.
. $(dirname "$(readlink -f "$0")")/outside_chroot_common.sh ||
  SCRIPT_ROOT=/usr/lib/crosutils

. "${SCRIPT_ROOT}/common.sh" ||
  (echo "Unable to load common.sh" && false) ||
  exit 1

. "${SCRIPT_ROOT}/remote_access.sh" || die "Unable to load remote_access.sh"

# Flags to control image_to_live.
DEFINE_boolean ignore_hostname ${FLAGS_TRUE} \
  "Ignore existing AU hostname on running instance use this hostname."
DEFINE_boolean ignore_version ${FLAGS_TRUE} \
  "Ignore existing version on running instance and always update."
DEFINE_string netdev "eth0" \
  "The network device to use for figuring out hostname. \
   This is useful on hosts with multiple NICs."
DEFINE_string server_log "dev_server.log" \
  "Path to log for the devserver."
DEFINE_boolean update "${FLAGS_TRUE}" \
  "Perform update of root partition."
DEFINE_boolean update_hostkey ${FLAGS_TRUE} \
  "Update your known_hosts with the new remote instance's key."
DEFINE_string update_log "update_engine.log" \
  "Path to log for the update_engine."
DEFINE_string update_url "" "Full url of an update image."
DEFINE_boolean verify ${FLAGS_TRUE} "Verify image on device after update."
DEFINE_integer repeat 1 "Number of times to run image_to_live."

# Flags for devserver.
DEFINE_string archive_dir "" \
  "Deprecated."
DEFINE_string board "" "Override the board reported by the target"
DEFINE_integer devserver_port 8080 \
  "Port to use for devserver."
DEFINE_boolean no_patch_kernel ${FLAGS_FALSE} \
  "Don't patch the kernel with verification blob from stateful. Prev: 'for_vm'"
DEFINE_string image "" \
  "Path to the image file to update with, xbuddy paths accepted." i
DEFINE_string payload "" \
  "Update with this update payload, ignoring specified images."
DEFINE_string proxy_port "" \
  "Have the client request from this proxy instead of devserver."
DEFINE_string src_image "" \
  "Create a delta update by passing in the image on the remote machine."
DEFINE_boolean update_stateful ${FLAGS_TRUE} \
  "Perform update of stateful partition e.g. /var /usr/local."
DEFINE_boolean reboot_after_update ${FLAGS_TRUE} \
  "Reboot after update applied for the update to take effect."

# Flags for stateful update.
DEFINE_string stateful_update_flag "" \
  "Flag to pass to stateful update e.g. old, clean, etc." s

FLAGS_HELP="
Usage: $0 --remote=[target_ip] [--image=[...]] ...
The remote flag is required to specify a ChromeOS machine to reimage.
The image flag can be a path to a local image or an XBuddy path.
For example:
  $0 --remote=172.0.0.0 --image=./some/path/to/chromium_test_image.bin
  Would reimage device at 172.0.0.0 with that locally available image.
  $0 --remote=172.0.0.0 --image='xbuddy:remote/parrot/latest/dev'
  Uses the latest developer parrot image available on Google Storage.
  $0 --remote=172.0.0.0 --image='xbuddy:release'
  Uses the latest test image available on Google Storage.
  $0 --remote=172.0.0.0 --image='xbuddy:'
  Uses the latest locally built image for the device board.
Please see http://goo.gl/6WdLrD for XBuddy documentation."

UPDATER_BIN="/usr/bin/update_engine_client"
UPDATER_IDLE="UPDATE_STATUS_IDLE"
UPDATER_NEED_REBOOT="UPDATE_STATUS_UPDATED_NEED_REBOOT"
UPDATER_UPDATE_CHECK="UPDATE_STATUS_CHECKING_FOR_UPDATE"
UPDATER_DOWNLOADING="UPDATE_STATUS_DOWNLOADING"

IMAGE_PATH=""
ROOTFS_MOUNTPT=""
STATEFUL_MOUNTPT=""

kill_all_devservers() {
  # Using ! here to avoid exiting with set -e is insufficient, so use
  # || true instead.
  sudo pkill -f devserver\.py || true
}

cleanup() {
  if [ -z "${FLAGS_update_url}" ]; then
    kill_all_devservers
  fi
  cleanup_remote_access
  sudo rm -rf "${TMP}" || true
  if [ ! -z "${ROOTFS_MOUNTPT}" ]; then
    rm -rf "${ROOTFS_MOUNTPT}"
  fi
  if [ ! -z "${STATEFUL_MOUNTPT}" ]; then
    rm -rf "${STATEFUL_MOUNTPT}"
  fi
}

remote_reboot_sh() {
  rm -f "${TMP_KNOWN_HOSTS}"
  remote_sh "$@"
}

# Returns the hostname of this machine.
# It tries to find the ipaddress using ifconfig, however, it will
# default to $HOSTNAME on failure.  We try to use the ip address first as
# some targets may have dns resolution issues trying to contact back
# to us.
get_hostname() {
  local hostname
  # Try to parse ifconfig for ip address. Use sudo, because not all distros
  # allow a common user to call ifconfig.
  # TODO(zbehan): What if target is not connected via eth0? Update over wifi?
  # Dedicated usb NIC? Perhaps this detection should be done in the target,
  # which will get the return address in one way or another. Or maybe we should
  # just open a ssh tunnel and use localhost.
  hostname=$(/sbin/ifconfig ${FLAGS_netdev} |
      grep 'inet addr' |
      cut -f2 -d':' |
      cut -f1 -d' ')

  # Fallback to $HOSTNAME if that failed
  [ -z "${hostname}" ] && hostname=${HOSTNAME}

  echo ${hostname}
}

is_xbuddy_path() {
  [[ "${FLAGS_image}" == xbuddy:* ]]
}

start_dev_server() {
  kill_all_devservers
  local devserver_flags="--pregenerate_update"
  # Parse devserver flags.
  if [ -n "${FLAGS_image}" ]; then
    if is_xbuddy_path; then
      info "Image flag is an xBuddy path to an image."
      devserver_flags="${devserver_flags} \
          --image ${FLAGS_image}"
    else
      info "Forcing the devserver to serve a local image."
      devserver_flags="${devserver_flags} \
          --image $(reinterpret_path_for_chroot ${FLAGS_image})"
      IMAGE_PATH="${FLAGS_image}"
    fi
  elif [ -n "${FLAGS_archive_dir}" ]; then
    echo "archive_dir flag is deprecated. Use --image."
    exit 1
  else
    # IMAGE_PATH should be the newest image and learn the board from
    # the target.
    learn_board
    IMAGE_PATH="$(${SCRIPTS_DIR}/get_latest_image.sh --board="${FLAGS_board}")"
    IMAGE_PATH="${IMAGE_PATH}/chromiumos_image.bin"
    devserver_flags="${devserver_flags} \
        --image $(reinterpret_path_for_chroot ${IMAGE_PATH})"
  fi

  if [ -n "${FLAGS_payload}" ]; then
    devserver_flags="${devserver_flags} \
        --payload $(reinterpret_path_for_chroot ${FLAGS_payload})"
  fi

  if [ -n "${FLAGS_proxy_port}" ]; then
    devserver_flags="${devserver_flags} \
        --proxy_port ${FLAGS_proxy_port}"
  fi

  if [ ${FLAGS_no_patch_kernel} -eq ${FLAGS_TRUE} ]; then
      devserver_flags="${devserver_flags} --no_patch_kernel"
  fi

  if [ -n "${FLAGS_src_image}" ]; then
    devserver_flags="${devserver_flags} \
        --src_image=\"$(reinterpret_path_for_chroot ${FLAGS_src_image})\""
  fi

  info "Starting devserver with flags ${devserver_flags}"

  # Clobber dev_server log in case image_to_live is run with sudo previously.
  if [ -f "${FLAGS_server_log}" ]; then
    sudo rm -f "${FLAGS_server_log}"
  fi

  # Need to inherit environment variables to discover gsutil credentials.
  cros_sdk -- sudo -E start_devserver ${devserver_flags} \
       --board=${FLAGS_board} \
       --port=${FLAGS_devserver_port} > ${FLAGS_server_log} 2>&1 &

  info "Waiting on devserver to start"
  info "note: be patient as the server generates the update before starting."
  until netstat -lnp 2>&1 | grep :${FLAGS_devserver_port} > /dev/null; do
    sleep 5
    echo -n "."
    if ! pgrep -f start_devserver > /dev/null; then
      echo "Devserver failed, see dev_server.log."
      exit 1
    fi
  done
  echo ""
}

# Copies stateful update script which fetches the newest stateful update
# from the dev server and prepares the update. chromeos_startup finishes
# the update on next boot.
run_stateful_update() {
  local dev_url=$(get_devserver_url)
  local stateful_url=""
  local stateful_update_args=""

  # Parse stateful update flag.
  if [ -n "${FLAGS_stateful_update_flag}" ]; then
    stateful_update_args="${stateful_update_args} \
        --stateful_change ${FLAGS_stateful_update_flag}"
  fi

  # Assume users providing an update url are using an archive_dir path.
  stateful_url=$(echo ${dev_url} | sed -e "s/update/static/")

  info "Starting stateful update using URL ${stateful_url}"

  # Copy over update script and run update.
  local chroot_path="${SCRIPTS_DIR}/../../chroot"
  local stateful_update_script="/usr/bin/stateful_update"

  remote_cp_to "${chroot_path}/${stateful_update_script}" "/tmp"
  remote_sh "/tmp/stateful_update ${stateful_update_args} ${stateful_url}"
}

get_update_args() {
  if [ -z ${1} ]; then
    die "No url provided for update."
  fi

  local update_args="--omaha_url ${1}"

  # Grab everything after last colon as an xbuddy path
  if is_xbuddy_path; then
    update_args="${update_args}/xbuddy/${FLAGS_image##*xbuddy:}"
  fi

  info "${update_args}"

  if [[ ${FLAGS_ignore_version} -eq ${FLAGS_TRUE} ]]; then
    info "Forcing update independent of the current version"
    update_args="--update ${update_args}"
  fi

  echo "${update_args}"
}

get_devserver_url() {
  local devserver_url=""
  local port=${FLAGS_devserver_port}

  if [[ -n ${FLAGS_proxy_port} ]]; then
    port=${FLAGS_proxy_port}
  fi

  if [ ${FLAGS_ignore_hostname} -eq ${FLAGS_TRUE} ]; then
    if [ -z ${FLAGS_update_url} ]; then
      devserver_url="http://$(get_hostname):${port}/update"
    else
      devserver_url="${FLAGS_update_url}"
    fi
  fi

  echo "${devserver_url}"
}

truncate_update_log() {
  remote_sh "> /var/log/update_engine.log"
}

get_update_log() {
  remote_sh "cat /var/log/update_engine.log"
  echo "${REMOTE_OUT}" > "${FLAGS_update_log}"
}

# Used to store the current update status of the remote update engine.
REMOTE_UPDATE_STATUS=

# Returns ${1} reported by the update client e.g. PROGRESS, CURRENT_OP.
get_var_from_remote_status() {
  echo "${REMOTE_UPDATE_STATUS}" |
      grep ${1} |
      cut -f 2 -d =
}

# Updates the remote status variable for the update engine.
update_remote_status() {
  remote_sh "${UPDATER_BIN} --status 2> /dev/null"
  REMOTE_UPDATE_STATUS="${REMOTE_OUT}"
}

# Both updates the remote status and gets the given variables.
get_update_var() {
  update_remote_status
  get_var_from_remote_status "${1}"
}

# Returns the current status / progress of the update engine.
# This is expected to run in its own thread.
status_thread() {
  local timeout=5

  info "Devserver handling ping.  Check ${FLAGS_server_log} for more info."
  sleep ${timeout}

  update_remote_status
  local current_state=""
  local next_state="$(get_var_from_remote_status CURRENT_OP)"

  # For current status, only print out status changes.
  # For download, show progress.
  # Finally if no status change print out .'s to keep dev informed.
  while [ "${current_state}" != "${UPDATER_NEED_REBOOT}" ] && \
      [ "${current_state}" != "${UPDATER_IDLE}" ]; do
    if [ "${current_state}" != "${next_state}" ]; then
      info "State of updater has changed to: ${next_state}"
    elif [ "${next_state}" = "${UPDATER_DOWNLOADING}" ]; then
      echo "Download progress $(get_var_from_remote_status PROGRESS)"
    else
      echo -n "."
    fi

    sleep ${timeout}
    current_state="${next_state}"
    update_remote_status
    next_state="$(get_var_from_remote_status CURRENT_OP)"
  done
}

# Dumps the update_engine log in real-time
log_thread() {
  echo 'starting log thread'
  # Using -t -t twice forces pseudo-tty allocation on the remote end, which
  # causes tail to go into line-buffered mode.
  EXTRA_REMOTE_SH_ARGS="-t -t" remote_sh_raw \
      "tail -n +0 -f /var/log/update_engine.log"
  echo 'stopping log thread'
}

# Pings the update_engine to see if it responds or a max timeout is reached.
# Returns 1 if max timeout is reached.
wait_until_update_engine_is_ready() {
  local wait_timeout=1
  local max_timeout=60
  local time_elapsed=0
  while ! get_update_var CURRENT_OP > /dev/null; do
    sleep ${wait_timeout}
    time_elapsed=$(( time_elapsed + wait_timeout ))
    echo -n "."
    if [ ${time_elapsed} -gt ${max_timeout} ]; then
      return 1
    fi
  done
}

run_auto_update() {
  # Truncate the update log so our log file is clean.
  truncate_update_log

  local update_args="$(get_update_args "$(get_devserver_url)")"
  info "Waiting to initiate contact with the update_engine."
  wait_until_update_engine_is_ready || die "Could not contact update engine."

  info "Starting update using args ${update_args}"

  # Sets up secondary threads to track the update progress and logs
  status_thread &
  local status_thread_pid=$!
  log_thread &
  local log_thread_pid=$!
  trap "kill -1 ${status_thread_pid} && kill -1 ${log_thread_pid} && cleanup" \
      EXIT INT TERM

  # Actually run the update.  This is a blocking call.
  remote_sh "${UPDATER_BIN} ${update_args}"

  # Clean up secondary threads.
  ! kill ${status_thread_pid} 2> /dev/null
  ! kill ${log_thread_pid} 2> /dev/null
  trap cleanup EXIT INT TERM

  local update_status="$(get_update_var CURRENT_OP)"
  if [ "${update_status}" = ${UPDATER_NEED_REBOOT} ]; then
    info "Autoupdate was successful."
    return 0
  else
    warn "Autoupdate was unsuccessful.  Status returned was ${update_status}."
    return 1
  fi
}

verify_image() {
  info "Verifying image."
  ROOTFS_MOUNTPT=$(mktemp -d)
  STATEFUL_MOUNTPT=$(mktemp -d)
  "${SCRIPTS_DIR}/mount_gpt_image.sh" --from "$(dirname "${IMAGE_PATH}")" \
                     --image "$(basename ${IMAGE_PATH})" \
                     --rootfs_mountpt="${ROOTFS_MOUNTPT}" \
                     --stateful_mountpt="${STATEFUL_MOUNTPT}" \
                     --read_only

  local lsb_release=$(cat ${ROOTFS_MOUNTPT}/etc/lsb-release)
  info "Verifying image with release:"
  echo ${lsb_release}

  "${SCRIPTS_DIR}/mount_gpt_image.sh" --unmount \
                     --rootfs_mountpt="${ROOTFS_MOUNTPT}" \
                     --stateful_mountpt="${STATEFUL_MOUNTPT}"

  remote_sh "cat /etc/lsb-release"
  info "Remote image reports:"
  echo ${REMOTE_OUT}

  if [ "${lsb_release}" = "${REMOTE_OUT}" ]; then
    info "Update was successful and image verified as ${lsb_release}."
    return 0
  else
    warn "Image verification failed."
    return 1
  fi
}

find_root_dev() {
  remote_sh "rootdev -s"
  echo ${REMOTE_OUT}
}

run_once() {
  if [ "$(get_update_var CURRENT_OP)" != "${UPDATER_IDLE}" ]; then
    warn "Machine is in a bad state.  Resetting the update_engine."
    remote_sh "${UPDATER_BIN} --reset_status 2> /dev/null"
  fi

  local initial_root_dev=$(find_root_dev)

  if [ -z "${FLAGS_update_url}" ]; then
    # Start local devserver if no update url specified.
    start_dev_server
  fi

  local update_pid
  if [ ${FLAGS_update} -eq ${FLAGS_TRUE} ]; then
    run_auto_update &
    update_pid=$!
  fi

  local stateful_pid
  local stateful_tmp_file
  if [ ${FLAGS_update_stateful} -eq ${FLAGS_TRUE} ]; then
    stateful_tmp_file=$(mktemp)
    run_stateful_update &> "${stateful_tmp_file}" &
    stateful_pid=$!
  fi

  if [ -n "${update_pid}" ] && ! wait ${update_pid}; then
    warn "Update failed. " \
       "Dumping update_engine.log for debugging and/or bug reporting."
    tail -n 200 "${FLAGS_update_log}" >&2
    die "Update was not successful."
  fi

  if [ -n "${stateful_pid}" ]; then
    local stateful_success=0
    if ! wait ${stateful_pid}; then
      stateful_success=1
    fi
    cat "${stateful_tmp_file}"
    rm "${stateful_tmp_file}"
    if [ ${stateful_success} -ne 0 ]; then
      die "Stateful update was not successful."
    fi
  fi

  if [ ${FLAGS_reboot_after_update} -eq ${FLAGS_FALSE} ]; then
    echo "Not rebooting because of --noreboot_after_update"
    print_time_elapsed
    return 0
  fi

  remote_reboot

  if [[ ${FLAGS_update_hostkey} -eq ${FLAGS_TRUE} ]]; then
    local known_hosts="${HOME}/.ssh/known_hosts"
    cp "${known_hosts}" "${known_hosts}~"
    grep -v "^${FLAGS_remote} " "${known_hosts}" > "${TMP}/new_known_hosts"
    cat "${TMP}/new_known_hosts" "${TMP_KNOWN_HOSTS}" > "${known_hosts}"
    chmod 0640 "${known_hosts}"
    info "New updated in ${known_hosts}, backup made."
  fi

  remote_sh "grep ^CHROMEOS_RELEASE_DESCRIPTION= /etc/lsb-release"
  if [ ${FLAGS_verify} -eq ${FLAGS_TRUE} ]; then
    verify_image

    if [ "${initial_root_dev}" == "$(find_root_dev)" ]; then
      # At this point, the software version didn't change, but we didn't
      # switch partitions either. Means it was an update to the same version
      # that failed.
      die "The root partition did NOT change. The update failed."
    fi
  else
    local release_description=$(echo ${REMOTE_OUT} | cut -d '=' -f 2)
    info "Update was successful and rebooted to $release_description"
  fi

  print_time_elapsed
}

main() {
  assert_outside_chroot

  cd "${SCRIPTS_DIR}"

  FLAGS "$@" || exit 1
  eval set -- "${FLAGS_ARGV}"

  set -e

  if [ ${FLAGS_verify} -eq ${FLAGS_TRUE} ] && \
      [ -n "${FLAGS_update_url}" ]; then
    warn "Verify is not compatible with setting an update url."
    FLAGS_verify=${FLAGS_FALSE}
  fi

  if [ ${FLAGS_verify} -eq ${FLAGS_TRUE} ] && \
      is_xbuddy_path; then
    warn "Verify is not currently compatible with xbuddy."
    FLAGS_verify=${FLAGS_FALSE}
  fi

  trap cleanup EXIT INT TERM

  TMP=$(mktemp -d /tmp/image_to_live.XXXX)

  remote_access_init

  for i in $(seq 1 ${FLAGS_repeat}); do
    echo "Iteration: " $i of ${FLAGS_repeat}
    run_once
    if [ ${FLAGS_repeat} -gt 1 ]; then
      remote_sh "${UPDATER_BIN} --reset_status 2> /dev/null"
    fi
  done

  exit 0
}

main $@
