#!/bin/bash
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


# Restarts web server by killing old pid and restarting through supervisorctl
supervisorctl restart chromeos_patches
