# Commits to revert on each topic branch *before* topic fixups
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Parts of the file are automatically generated
# pylint: disable=line-too-long

"""automatic rebase-specific data"""

import hooks  # pylint: disable=unused-import


verify_board = 'volteer'
verify_package = 'chromeos-kernel-upstream'
rebase_repo = 'kernel-upstream'
baseline_repo = 'baseline/kernel-upstream/'

global_reverts = []

commit_hooks = {}
# calls a function on a selection of events, listed in the 'types' list.
# the different types are as follows:
# - conflict: called if a patch conflicts.
# - pre: called before the patch is applied.
# - post: called after successful application.
# - post_empty: called after a successful application that causes the commit to
#               be empty.
# - post_drop: called after triage drops a conflicting commit.
# The hook can be applied either only for a given commit (set the key to its SHA)
# or to all commits (set the key to '*')
# examples:
#   commit_hooks['e0c3be8f6bce'] = {'hook': hooks.pause, 'types': ['post']}
#   commit_hooks['*'] = {'hook': hooks.pause, 'types': ['conflict']}
# commit_hooks['a49b8bb6e63d'] = {'hook': hooks.pause, 'types': ['pre']}

topic_fixups = {}
# example:
# topic_fixups['bluetooth'] = ['fd83ec5d9b94']

topic_fixups['arch'] = [
    'KVM: mmu: introduce new gfn_to_pfn_page functions',
    'KVM: Fix multiple races in gfn=>pfn cache refresh',
    'FIXUP: KVM: mmu: introduce new gfn_to_pfn_page functions'
]

topic_fixups['chromeos'] = [
    'mm: Optionally limit per-process reclaim',
    'FROMLIST: sched: Add a coresched command line option',
]

topic_fixups['bluetooth'] = [
    'devcoredump: Add per device sysfs entry to enable disable coredump'
]

topic_fixups['block-fs'] = [
    'Add message definitions for CHROMEOS_TMPFILE',
    'FIXUP-CHROMIUM-drivers-md-dm-verity-chromeos-Fix-bio',
]

topic_fixups['cros_ec'] = [
    'platform: x86: add ACPI driver for ChromeOS',
]

# order for automatic branch merging in rebase.py.
# branches that aren't specified are merged in an unspecified order.
# example that first merges drm, then gpu/other, then others:
# merge_order_override = [
#     "drm",
#     "gpu/other"
# ]
merge_order_override = [
]

# patches to be cherry-picked after automatic merge
# example:
# merge_fixups = [
#     "e0783589ae58"
# ]
merge_fixups = [
]

# cherry-pick a list of patches before a given patch
# during automatic rebase.
# example:
# patch_deps = {
#     '0d022b4a1e19': ['6e18e51a1c19']
# }
patch_deps = {
      '4638c45ac4c3': ['be850241385f'],
      'a0b6f18f6f99': ['1b11975955e5', '2e1d95fe697e'],
      '9374b3da44f7': ['a8d5ee3cd35c'],
      'dba4f3cbb765': ['f1c5e6917f73'],
      '343cf85ba839': ['85634c066fc3'],
      'e8eba5950370': ['ff52d46e7dbb'],
}

# Add entry here to overwrite default disposition on particular commit
# WARNING: lines can be automatically appended here when user chooses
# to drop the commit from rebase script.
disp_overlay = {}
# example
# disp_overlay['62b865c66db4'] = 'drop'

disp_overlay['361e832d5127'] = 'drop' # Revert "UPSTREAM: Bluetooth: hci_qca: Add device_may_wakeup support"
disp_overlay['d3ca0f8f9181'] = 'drop' # BACKPORT: UPSTREAM: Bluetooth: hci_qca: Add device_may_wakeup support
disp_overlay['5a46f9f5770f'] = 'drop' # FROMLIST: fuse: 32-bit user space ioctl compat for fuse device
disp_overlay['ff52d46e7dbb'] = 'drop' # FROMLIST: i2c: designware: Switch from using MMIO access to SMN access
disp_overlay['5bbe10aab447'] = 'drop' # FROMLIST: mailbox: mtk-cmdq: instead magic number with GCE_CTRL_BY_SW
disp_overlay['2f1d896c09eb'] = 'drop' # FIXUP: FROMLIST: sched: Add a coresched command line option
disp_overlay['20dda512a08f'] = 'drop' # CHROMIUM: drm/udl: Cut >165 MHz modes for DVI
