# -*- coding: utf-8 -*-
# Copyright 2018 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Configuration file for syzbot-autotriager."""

# syzkaller bug dbs.
ISSUETRACKER_DB = 'issuetracker.db'
SYZWEB_DB = 'syzweb.db'

# linux kernel commit dbs.
SRC_LINUX_DB = 'linux.db'
SRC_V414_DB = 'v414.db'
SRC_V44_DB = 'v44.db'
SRC_V318_DB = 'v318.db'
SRC_V314_DB = 'v314.db'
SRC_V310_DB = 'v310.db'
SRC_V38_DB = 'v38.db'

SRC_LINUX_STABLE_414_DB = 'linux-414-stable.db'
SRC_LINUX_STABLE_44_DB = 'linux-44-stable.db'

CROS_ROOT = '~/chromiumos'
LINUX = '~/repos/kernels/linux'   # Change this.
LINUX_STABLE = '~/repos/kernels/linux-stable' # Change this.
