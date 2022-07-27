#!/bin/bash
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FINDMISSING_DIR="${HOME}/findmissing_workspace/findmissing"
cd "${FINDMISSING_DIR}"

rm -rf __pycache__/ env/
