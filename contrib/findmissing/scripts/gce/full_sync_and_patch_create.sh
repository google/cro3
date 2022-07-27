#!/bin/bash
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


FINDMISSING_DIR="${HOME}/findmissing_workspace/findmissing"
cd "${FINDMISSING_DIR}"

if [[ ! -e env/bin/activate ]]; then
    echo "Virtual environment not set up."
    echo "Setting up virtual environment"
    python3 -m venv env
    source env/bin/activate

    # pip install requirements line by line
    pip install -q $(cat requirements.txt)
else
    source env/bin/activate
fi

LOG_FILE="/var/log/findmissing/findmissing.log"
LAST_CREATE="/tmp/synchronize-lastrun"

day="$(date +%e)"
create="False"
if [[ ! -e "${LAST_CREATE}" ]]; then
    create="True"
else
    last="$(cat ${LAST_CREATE})"
    if [[ "${last}" != "${day}" ]]; then
        create="True"
    fi
fi

echo "${day}" > "${LAST_CREATE}"

echo "Triggered full synchronization at $(date)" >> ${LOG_FILE}
env/bin/python3 -c "import main; main.synchronize_and_create_patches(${create})" >> ${LOG_FILE} 2>&1
echo -e "\n" >> ${LOG_FILE}
