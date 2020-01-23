# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing kernels configuration information."""

KERNEL_SITE = 'https://git.kernel.org/'
UPSTREAM_REPO = KERNEL_SITE + 'pub/scm/linux/kernel/git/torvalds/linux'
STABLE_REPO = KERNEL_SITE + 'pub/scm/linux/kernel/git/stable/linux-stable'

CHROMIUM_SITE = 'https://chromium.googlesource.com/'
CHROMEOS_REPO = CHROMIUM_SITE + 'chromiumos/third_party/kernel'

STABLE_BRANCHES = ('4.4', '4.14', '4.19', '5.4')
STABLE_PATTERN = 'linux-%s.y'

CHROMEOS_BRANCHES = ('4.4', '4.14', '4.19', '5.4')
CHROMEOS_PATTERN = 'chromeos-%s'

CHROMEOS_PATH = 'linux-chrome'
STABLE_PATH = 'linux-stable'
UPSTREAM_PATH = 'linux-upstream'
