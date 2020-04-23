#!/bin/bash
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


FINDMISSING_DIR=$(cd $(dirname $0)/../..; pwd)
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

LOG_FILE=/var/log/findmissing.log

echo "Triggered full synchronization at $(date)\n" >> ${LOG_FILE}
env/bin/python3 -c 'import main; main.synchronize_and_create_patches()' >> ${LOG_FILE} 2>&1
echo -e "\n" >> ${LOG_FILE}
