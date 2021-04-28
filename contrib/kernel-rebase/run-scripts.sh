#!/bin/bash
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

baseline="$(python3 -c 'from config import rebase_baseline_branch; print(rebase_baseline_branch)')"

progdir=$(dirname "$0")
logfile="/tmp/run-scripts.${baseline}.$(date +%F).log"

# IT loves uninstalling stuff, so just force a reinstall
pip3 install google_auth_oauthlib python-Levenshtein fuzzywuzzy >/dev/null 2>&1

cd "${progdir}" || exit 1
./setup.sh > "${logfile}" 2>&1
./genspreadsheet.py >> "${logfile}" 2>&1
./genstats.py >> "${logfile}" 2>&1
