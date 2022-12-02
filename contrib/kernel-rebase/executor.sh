#!/bin/bash

# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# the path as seen from the SDK
cd "$(dirname "$0")" || exit

IO=$(python3 -c "from common import executor_io; print(executor_io)")

mkdir -p "${IO}"
function cleanup {
  rm -rf "${IO}"
}
trap cleanup EXIT

rm -f "${IO}"/output
rm -f "${IO}"/commands
mkfifo "${IO}"/output
mkfifo "${IO}"/commands
while true
do
# cat is not equivalent to < when the file is a FIFO
# shellcheck disable=SC2002
  commands=$(cat "${IO}"/commands)
  echo "$(date '+%Y-%m-%d %H:%M:%S'): executing ${commands}"
  echo "${commands}" | bash > "${IO}"/output
  echo $? > "${IO}"/last_exit
  echo "$(date '+%Y-%m-%d %H:%M:%S'): returncode ${?}"
done
