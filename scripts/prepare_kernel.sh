#!/bin/bash -e

which xxd >/dev/null || {
  echo "Please install 'xxd' command!"
  exit 1
}

function set_rootpart_vars() {
  echo "Using DUT=${DUT}"
  PART_ROOT_LIVE=$(cro3 dut shell --dut "${DUT}" -- rootdev -s)
  echo "Using PART_ROOT_LIVE=${PART_ROOT_LIVE}"
  ROOTDEV_PART_BASE=$(echo "${PART_ROOT_LIVE}" | sed -E -e 's/3$//' -e 's/5$//')
  ROOTDEV=$(echo "${ROOTDEV_PART_BASE}" | sed -E -e 's/p$//')
  echo "Using ROOTDEV=${ROOTDEV}"
  echo "Using ROOTDEV_PART_BASE=${ROOTDEV_PART_BASE}"
  PART_KERN_A="${ROOTDEV_PART_BASE}2"
  PART_ROOT_A="${ROOTDEV_PART_BASE}3"
  PART_KERN_B="${ROOTDEV_PART_BASE}4"
  PART_ROOT_B="${ROOTDEV_PART_BASE}5"
  echo "PART_KERN_A=${PART_KERN_A}"
  echo "PART_ROOT_A=${PART_ROOT_A}"
  echo "PART_KERN_B=${PART_KERN_B}"
  echo "PART_ROOT_B=${PART_ROOT_B}"
}

function get_current_kernel_cmdline() {
  echo "Using DUT=${DUT}"
  echo "Using ROOTDEV=${ROOTDEV}"
  echo "=> PART_KERN_A=${PART_KERN_A}"
  echo "=> PART_KERN_B=${PART_KERN_B}"
  CMDLINE_KERN_A="$(cro3 dut shell --dut "${DUT}" -- futility vbutil_kernel --verify "${PART_KERN_A}" | tail -n 1)"
  CMDLINE_KERN_B="$(cro3 dut shell --dut "${DUT}" -- futility vbutil_kernel --verify "${PART_KERN_B}" | tail -n 1)"
  echo "=> CMDLINE_KERN_A='${CMDLINE_KERN_A}'"
  echo "=> CMDLINE_KERN_B='${CMDLINE_KERN_B}'"
  diff -y <(echo "${CMDLINE_KERN_A}" | tr ' ' '\n') <(echo "${CMDLINE_KERN_B}" | tr ' ' '\n') || true
}

# c.f. https://chromium.googlesource.com/chromiumos/platform/crosutils/+/main/bin/cros_make_image_bootable
function change_ro_to_rw() {
  sed -E -e 's/ ro / rw /'
}
function change_mitigations_auto() {
  # https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html?highlight=kernel%20parameters#:~:text=2.6/mini2440.git-,mitigations,-%3D%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%5BX86%2CPPC%2CS390
  sed -E -e 's/( mitigations=.*$)|$/ l1tf=off/'
}
function change_mitigations_off() {
  # https://www.kernel.org/doc/html/latest/admin-guide/kernel-parameters.html?highlight=kernel%20parameters#:~:text=2.6/mini2440.git-,mitigations,-%3D%0A%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%20%5BX86%2CPPC%2CS390
  sed -E -e 's/( mitigations=.*$)|$/ /'
}
function set_cros_debug() {
  sed -E -e 's/( cros_debug)|$/ cros_debug/'
}

function extract_cros_lsb_release_hash_from_cmdline() {
  sed 's/ /\n/g' | grep '^cros_lsb_release_hash=' | cut -d '=' -f 2
}

function verify_booting_kernel_matches_with_lsb_release() {
  # Make sure the installed kernels are valid ones that comes from the currently-installed ChromeOS.
  HASH_FROM_BOOTING_KERNEL=$(cro3 dut shell --dut "${DUT}" -- cat /proc/cmdline | extract_cros_lsb_release_hash_from_cmdline)
  echo "HASH_FROM_BOOTING_KERNEL=${HASH_FROM_BOOTING_KERNEL}"
  HASH_FROM_KERN_A=$(cro3 dut shell --dut "${DUT}" -- vbutil_kernel --verify "${PART_KERN_A}" | extract_cros_lsb_release_hash_from_cmdline)
  echo "HASH_FROM_KERN_A=${HASH_FROM_KERN_A}"
  HASH_FROM_KERN_B=$(cro3 dut shell --dut "${DUT}" -- vbutil_kernel --verify "${PART_KERN_B}" | extract_cros_lsb_release_hash_from_cmdline)
  echo "HASH_FROM_KERN_B=${HASH_FROM_KERN_B}"
  HASH_FROM_LSB_RELEASE=$(cro3 dut shell --dut "${DUT}" -- sha256sum -b /etc/lsb-release | cut -d ' ' -f 1 | xxd -r -p | base64 -w 0 | tr -d '=')
  echo "HASH_FROM_LSB_RELEASE=${HASH_FROM_LSB_RELEASE}"

  if [ "${HASH_FROM_KERN_A}" = "${HASH_FROM_LSB_RELEASE}" ]; then
    echo "KERN_A seems to match with the active rootfs"
    if [ "${HASH_FROM_KERN_B}" = "${HASH_FROM_LSB_RELEASE}" ]; then
      echo "KERN_B seems to be matched with the active the rootfs"
    else
      if [ "${PART_ROOT_B}" = "${PART_ROOT_LIVE}" ]; then
        echo "Kernel / RootFS B should be fixed but is live. Please reboot into another partition first by:"
        exit 1
      else
        echo "KERN_B should be fixed. run:"
        echo "cro3 dut shell --dut ${DUT} -- dd if=${PART_KERN_A} of=${PART_KERN_B} bs=4M status=progress"
        echo "cro3 dut shell --dut ${DUT} -- dd if=${PART_ROOT_A} of=${PART_ROOT_B} bs=4M status=progress"
        echo "cro3 dut shell --dut ${DUT} -- fsck -y -l ${PART_ROOT_B}"
        echo "cro3 dut shell --dut ${DUT} -- reboot"
        exit 1
      fi
    fi
  else
    if [ "${HASH_FROM_KERN_B}" = "${HASH_FROM_LSB_RELEASE}" ]; then
      if [ "${PART_ROOT_A}" = "${PART_ROOT_LIVE}" ]; then
        echo "Kernel / RootFS A should be fixed but is live. Please reboot into another partition first by:"
        exit 1
      else
        echo "KERN_B seems to match with the rootfs"
        echo "KERN_A should be fixed to match with B. run:"
        echo "cro3 dut shell --dut ${DUT} -- dd if=${PART_KERN_B} of=${PART_KERN_A} bs=4M status=progress"
        echo "cro3 dut shell --dut ${DUT} -- dd if=${PART_ROOT_B} of=${PART_ROOT_A} bs=4M status=progress"
        echo "cro3 dut shell --dut ${DUT} -- fsck -y -l ${PART_ROOT_A}"
        echo "cro3 dut shell --dut ${DUT} -- reboot"
        exit 1
      fi
    else
      echo "No kernel seems to be matched with the rootfs. Please try flashing a new image again."
      exit 1
    fi
  fi
  echo "To switch to use KERN_A, run:"
  echo "cro3 dut shell --dut ${DUT} -- cgpt prioritize -i 2 ${ROOTDEV}"
  echo "To switch to use KERN_B, run:"
  echo "cro3 dut shell --dut ${DUT} -- cgpt prioritize -i 4 ${ROOTDEV}"
  echo "And run this command to reboot (and pray...)"
  echo "cro3 dut do --dut ${DUT} reboot"
}

function update_kernel_cmdline() {
  set +e
  DIFF_A="$(wdiff --no-common <(echo "${CMDLINE_KERN_A}") <(echo "${NEW_CMDLINE_KERN_A}"))"
  DIFF_A_CODE=$?
  DIFF_B="$(wdiff --no-common <(echo "${CMDLINE_KERN_B}") <(echo "${NEW_CMDLINE_KERN_B}"))"
  DIFF_B_CODE=$?
  set -e
  if [ "${DIFF_A_CODE}" -eq "0" ] && [ "${DIFF_B_CODE}" -eq "0" ] ; then
      echo "No need to update the kernel cmdline."
  echo "${DUT}: $(wdiff --no-common <(echo "${CMDLINE_KERN_A}") <(echo "${CMDLINE_KERN_B}") | tail -n -2 | head -n 1)" >&2 || true
      exit 0
  fi

  echo "updating the kernel cmdline"
  PATH_NEW_CMDLINE_BASE=$(mktemp --tmpdir=/tmp kernel_cmdline_XXXXXXXXXX)
  PATH_NEW_CMDLINE_KERN_A="${PATH_NEW_CMDLINE_BASE}".2
  PATH_NEW_CMDLINE_KERN_B="${PATH_NEW_CMDLINE_BASE}".4
  echo "${NEW_CMDLINE_KERN_A}" >"${PATH_NEW_CMDLINE_KERN_A}"
  echo "${NEW_CMDLINE_KERN_B}" >"${PATH_NEW_CMDLINE_KERN_B}"
  ls -lah "${PATH_NEW_CMDLINE_KERN_A}"
  cat "${PATH_NEW_CMDLINE_KERN_A}"
  ls -lah "${PATH_NEW_CMDLINE_KERN_B}"
  cat "${PATH_NEW_CMDLINE_KERN_B}"
  cro3 dut push --dest /tmp/ --dut "${DUT}" "${PATH_NEW_CMDLINE_KERN_A}" "${PATH_NEW_CMDLINE_KERN_B}"
  cro3 dut shell --dut "${DUT}" -- /usr/share/vboot/bin/make_dev_ssd.sh --partitions 2 --set_config "${PATH_NEW_CMDLINE_BASE}"
  cro3 dut shell --dut "${DUT}" -- /usr/share/vboot/bin/make_dev_ssd.sh --partitions 4 --set_config "${PATH_NEW_CMDLINE_BASE}"
}

function gen_new_kernel_cmdline() {
  CMDLINE_COMMON_PART="$(wdiff <(echo ${CMDLINE_KERN_A}) <(echo ${CMDLINE_KERN_B}) --no-deleted --no-inserted | head -n 1)"
  echo "=> CMDLINE_COMMON_PART='${CMDLINE_COMMON_PART}'"
  NEW_CMDLINE_KERN_A="$(echo "${CMDLINE_COMMON_PART}" | change_ro_to_rw | change_mitigations_auto | set_cros_debug)"
  NEW_CMDLINE_KERN_B="$(echo "${CMDLINE_COMMON_PART}" | change_ro_to_rw | change_mitigations_off | set_cros_debug)"
  echo "=> NEW_CMDLINE_KERN_A='${NEW_CMDLINE_KERN_A}'"
  echo "=> NEW_CMDLINE_KERN_B='${NEW_CMDLINE_KERN_B}'"
  echo "DIFF of new cmdline:"
  diff -y <(echo "${NEW_CMDLINE_KERN_A}" | tr ' ' '\n') <(echo "${NEW_CMDLINE_KERN_B}" | tr ' ' '\n') || true
  echo "DIFF of new cmdline end:"
}

function print_mitigation_list() {
	cro3 dut "do" --dut "${DUT}" -- switch_to_boot_from_kernel_a reboot wait_online
	VULN_LIST_A="$(cro3 dut shell --dut ${DUT} -- bash -c '"cat /proc/cmdline ; lscpu | grep Vuln"')"
	echo "${VULN_LIST_A}"

	cro3 dut "do" --dut "${DUT}" -- switch_to_boot_from_kernel_b reboot wait_online
	VULN_LIST_B="$(cro3 dut shell --dut ${DUT} -- bash -c '"cat /proc/cmdline ; lscpu | grep Vuln"')"
	echo "${VULN_LIST_B}"

	echo "DIFF of vulnerabilities:"
	diff -y <(echo "${VULN_LIST_A}") <(echo "${VULN_LIST_B}") || true
	echo "DIFF of vulnerabilities end:"
}

DUT="$1"

set_rootpart_vars
verify_booting_kernel_matches_with_lsb_release
get_current_kernel_cmdline
gen_new_kernel_cmdline
update_kernel_cmdline
print_mitigation_list
