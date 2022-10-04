#!/bin/bash
#
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FINDMISSING="$(cd "$(dirname "$0")" || exit; pwd)"
cd "${FINDMISSING}" || exit

WORKSPACE="${HOME}/findmissing_workspace"
PYTHON_CMD="./$(basename "$0").py"

if [[ ! -e ${WORKSPACE}/env/bin/activate ]]; then
    echo "Environment is not set up to run findmissing client."
    echo "Please run './scripts/local/local_setup.sh' and repeat this command"
    exit 1
fi

# shellcheck disable=SC1091
source "${WORKSPACE}/env/bin/activate"

# Run script with parameters in virtual env
exec "${PYTHON_CMD}" "$@"
