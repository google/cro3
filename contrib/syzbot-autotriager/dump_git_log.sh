#!/bin/bash
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

PATH_414="${CROS_ROOT}/src/third_party/kernel/v4.14"
PATH_44="${CROS_ROOT}/src/third_party/kernel/v4.4"
PATH_318="${CROS_ROOT}/src/third_party/kernel/v3.18"
PATH_314="${CROS_ROOT}/src/third_party/kernel/v3.14"
PATH_310="${CROS_ROOT}/src/third_party/kernel/v3.10"
PATH_38="${CROS_ROOT}/src/third_party/kernel/v3.8"

checkout_pull() {
  cd "$1" || exit
  git checkout "$2"
  git pull origin "$2"
  git log --name-only > "$3"
}

checkout_pull "${LINUX}" master "${TFILE_0}"

checkout_sync() {
  cd "$1" || exit
  git checkout "$2"
  repo sync .
  git log --name-only > "$3"
}

checkout_sync "${PATH_414}" cros/chromeos-4.14 "${TFILE_1}"
checkout_sync "${PATH_44}"  cros/chromeos-4.4  "${TFILE_2}"
checkout_sync "${PATH_318}" cros/chromeos-3.18 "${TFILE_3}"
checkout_sync "${PATH_314}" cros/chromeos-3.14 "${TFILE_4}"
checkout_sync "${PATH_310}" cros/chromeos-3.10 "${TFILE_5}"
checkout_sync "${PATH_38}"  cros/chromeos-3.8  "${TFILE_6}"

checkout_pull "${LINUXSTABLE}" linux-4.14.y "${TFILE_7}"
checkout_pull "${LINUXSTABLE}" linux-4.4.y "${TFILE_8}"
