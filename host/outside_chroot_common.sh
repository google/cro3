#!/bin/bash

# Copyright (c) 2011 Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Sets script_root relative to this directory.

# From platform/dev/host.
if [ -f /etc/debian_chroot ]; then
  echo "Must be run from outside the chroot." 2> /dev/null
  exit 1
fi

SCRIPT_ROOT="$(dirname "$(readlink -f "$0")")/../../scripts"

