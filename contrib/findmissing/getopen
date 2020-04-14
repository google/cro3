#!/bin/bash
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FINDMISSING_DIR="$(cd "$(dirname "$0")" || exit; pwd)"
PYTHON_CMD="./$(basename "$0").py"

cd "${FINDMISSING_DIR}" || exit 1
if [[ ! -e env/bin/activate ]]; then
    echo "Environment is not set up to run findmissing client."
    echo "Please run './scripts/local/local_database_setup.sh' and repeat this command"
    exit 1
fi

source env/bin/activate

# Run script with parameters in virtual env
exec "${PYTHON_CMD}" "$@"
