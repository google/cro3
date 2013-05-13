#!/bin/bash
#
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# A test script for paycheck.py and the update_payload.py library.
#
# This script requires three payload files, along with a metadata signature for
# each, and a public key for verifying signatures. Payload include:
#
# - A full payload for release X (old_full_payload)
#
# - A full payload for release Y (new_full_payload), where Y > X
#
# - A delta payload from X to Y (delta_payload)
#
# The test performs the following:
#
# - It verifies each payload against its metadata signature, also asserting the
#   payload type. Another artifact is a human-readable payload report, which
#   is output to stdout to be inspected by the user.
#
# - It performs a random block trace on the delta payload (both kernel and
#   rootfs blocks), dumping the traces to stdout for the user to inspect.
#
# - It applies old_full_payload to yield old kernel (old_kern.part) and rootfs
#   (old_root.part) partitions.
#
# - It applies delta_payload to old_{kern,root}.part to yield new kernel
#   (new_delta_kern.part) and rootfs (new_delta_root.part) partitions.
#
# - It applies new_full_payload to yield reference new kernel
#   (new_full_kern.part) and rootfs (new_full_root.part) partitions.
#
# - It compares new_{delta,full}_kern.part and new_{delta,full}_root.part to
#   ensure that they are binary identical.
#
# If all steps have completed successfully we know with high certainty that
# paycheck.py (and hence update_payload.py) correctly parses both full and
# delta payloads, and applies them to yield the expected result. We also know
# that tracing works, to the extent it does not crash. Manual inspection of
# payload reports and block traces will improve this our confidence and are
# strongly encouraged. Finally, each paycheck.py execution is timed.


# Stop on errors, unset variables.
set -e
set -u

# Temporary image files.
OLD_KERN_PART=old_kern.part
OLD_ROOT_PART=old_root.part
NEW_DELTA_KERN_PART=new_delta_kern.part
NEW_DELTA_ROOT_PART=new_delta_root.part
NEW_FULL_KERN_PART=new_full_kern.part
NEW_FULL_ROOT_PART=new_full_root.part


log() {
  echo "$@" >&2
}

die() {
  log "$@"
  exit 1
}

usage_and_exit() {
  cat >&2 <<EOF
Usage: ${0##*/} old_full_payload delta_payload new_full_payload
EOF
  exit
}

check_payload() {
  payload_file=$1
  payload_type=$2

  time ${paycheck} -t ${payload_type} ${payload_file}
}

trace_kern_block() {
  payload_file=$1
  block=$2
  time ${paycheck} -B ${block} ${payload_file}
}

trace_root_block() {
  payload_file=$1
  block=$2
  time ${paycheck} -b ${block} ${payload_file}
}

apply_full_payload() {
  payload_file=$1
  dst_kern_part="$2/$3"
  dst_root_part="$2/$4"

  time ${paycheck} ${payload_file} ${dst_kern_part} ${dst_root_part}
}

apply_delta_payload() {
  payload_file=$1
  dst_kern_part="$2/$3"
  dst_root_part="$2/$4"
  src_kern_part="$2/$5"
  src_root_part="$2/$6"

  time ${paycheck} ${payload_file} ${dst_kern_part} ${dst_root_part} \
    ${src_kern_part} ${src_root_part}
}

main() {
  # Read command-line arguments.
  if [ $# == 1 ] && [ "$1" == "-h" ]; then
    usage_and_exit
  elif [ $# != 3 ]; then
    die "Error: unexpected number of arguments"
  fi
  old_full_payload="$1"
  delta_payload="$2"
  new_full_payload="$3"

  # Find paycheck.py
  paycheck=${0%/*}/paycheck.py
  if [ -z "${paycheck}" ] || [ ! -x ${paycheck} ]; then
    die "cannot find ${paycheck} or file is not executable"
  fi

  # Check the payloads statically.
  log "Checking payloads..."
  check_payload "${old_full_payload}" full
  check_payload "${new_full_payload}" full
  check_payload "${delta_payload}" delta
  log "Done"

  # Trace a random block between 0-1024 on all payloads.
  block=$((RANDOM * 1024 / 32767))
  log "Tracing a random block (${block}) in full/delta payloads..."
  trace_kern_block "${new_full_payload}" ${block}
  trace_root_block "${new_full_payload}" ${block}
  trace_kern_block "${delta_payload}" ${block}
  trace_root_block "${delta_payload}" ${block}
  log "Done"

  # Apply full/delta payloads and verify results are identical.
  tmpdir="$(mktemp -d --tmpdir test_paycheck.XXXXXXXX)"
  log "Initiating application of payloads at $tmpdir"

  log "Applying old full payload..."
  apply_full_payload "${old_full_payload}" "${tmpdir}" "${OLD_KERN_PART}" \
    "${OLD_ROOT_PART}"
  log "Done"

  log "Applying delta payload to old partitions..."
  apply_delta_payload "${delta_payload}" "${tmpdir}" "${NEW_DELTA_KERN_PART}" \
    "${NEW_DELTA_ROOT_PART}" "${OLD_KERN_PART}" "${OLD_ROOT_PART}"
  log "Done"

  log "Applying new full payload..."
  apply_full_payload "${new_full_payload}" "${tmpdir}" "${NEW_FULL_KERN_PART}" \
    "${NEW_FULL_ROOT_PART}"
  log "Done"

  log "Comparing results of delta and new full updates..."
  diff "${tmpdir}/${NEW_FULL_KERN_PART}" "${tmpdir}/${NEW_DELTA_KERN_PART}"
  diff "${tmpdir}/${NEW_FULL_ROOT_PART}" "${tmpdir}/${NEW_DELTA_ROOT_PART}"
  log "Done"

  log "Cleaning up"
  rm -fr "${tmpdir}"
}

main "$@"
