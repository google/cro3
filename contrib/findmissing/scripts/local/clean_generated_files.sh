#!/bin/bash
#
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FINDMISSING_DIR="${HOME}/findmissing_workspace/findmissing"
cd "${FINDMISSING_DIR}" || exit

rm -rf __pycache__/ env/
