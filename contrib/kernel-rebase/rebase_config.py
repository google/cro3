# Commits to revert on each topic branch *before* topic fixups
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Parts of the file are automatically generated
# pylint: disable=line-too-long

"""automatic rebase-specific data"""

import hooks  # pylint: disable=unused-import


verify_board = "volteer"
verify_package = "chromeos-kernel-upstream"
rebase_repo = "kernel-upstream"
baseline_repo = "baseline/kernel-upstream/"

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

topic_patches = {}
# patches and fixups applied on top of each topic branch
#
# examples:
# topic_patches['arch'] = [
#    'patches/KVM: mmu: introduce new gfn_to_pfn_page functions.patch',
# ]
#
# topic_patches['cros_ec'] = [
#    'fixups/platform: x86: add ACPI driver for ChromeOS.patch',
# ]

topic_patches["block-fs"] = [
    "fixups/FIXUP-CHROMIUM-drivers-md-dm-verity-chromeos-Fix-bio.patch",
]

topic_patches["cros_ec"] = [
    "fixups/platform: x86: add ACPI driver for ChromeOS.patch",
]

topic_patches["gpu/other"] = [
    "fixups/CHROMIUM: gpu: mali: Apply r40p0 EAC release 1.patch",
    "fixups/CHROMIUM: gpu: mali: Apply r40p0 EAC release 2.patch",
]

topic_patches["mm"] = [
    "fixups/CHROMIUM: Reland of add implementation of MGLRU in sysfs.patch",
    "fixups/CHROMIUM: mm: per-process reclaim.patch",
    "fixups/FROMLIST: Add flags option to get xattr method paired to __vfs_getxattr.patch",
]

topic_patches["drivers"] = [
    "fixups/FROMGIT: xhci: check for a pending command completion during command timeout.patch",
]

# order for automatic branch merging in rebase.py.
# branches that aren't specified are merged in an unspecified order.
# example that first merges drm, then gpu/other, then others:
# merge_order_override = [
#     "drm",
#     "gpu/other"
# ]
merge_order_override = []

# patches to be cherry-picked after automatic merge
# example:
# merge_fixups = [
#     "e0783589ae58"
# ]
merge_fixups = []

# cherry-pick a list of patches before a given patch
# during automatic rebase.
# example:
# patch_deps = {
#     '0d022b4a1e19': ['6e18e51a1c19']
# }
patch_deps = {
    "4638c45ac4c3": ["be850241385f"],
    "a0b6f18f6f99": ["1b11975955e5", "2e1d95fe697e"],
    "9374b3da44f7": ["a8d5ee3cd35c"],
    "dba4f3cbb765": ["f1c5e6917f73"],
    "343cf85ba839": ["85634c066fc3"],
    "e8eba5950370": ["ff52d46e7dbb"],
    "0e90656c5af0": ["49631570c04c"],
}

# Add entry here to overwrite default disposition on particular commit
# WARNING: lines can be automatically appended here when user chooses
# to drop the commit from rebase script.
disp_overwrite = {}
# example
# disp_overwrite['62b865c66db4'] = 'drop'

disp_overwrite[
    "361e832d5127"
] = "drop"  # Revert "UPSTREAM: Bluetooth: hci_qca: Add device_may_wakeup support"
disp_overwrite[
    "d3ca0f8f9181"
] = "drop"  # BACKPORT: UPSTREAM: Bluetooth: hci_qca: Add device_may_wakeup support
disp_overwrite[
    "5a46f9f5770f"
] = "drop"  # FROMLIST: fuse: 32-bit user space ioctl compat for fuse device
disp_overwrite[
    "ff52d46e7dbb"
] = "drop"  # FROMLIST: i2c: designware: Switch from using MMIO access to SMN access
disp_overwrite[
    "5bbe10aab447"
] = "drop"  # FROMLIST: mailbox: mtk-cmdq: instead magic number with GCE_CTRL_BY_SW
disp_overwrite[
    "20dda512a08f"
] = "drop"  # CHROMIUM: drm/udl: Cut >165 MHz modes for DVI
disp_overwrite["c5daa007043c"] = [
    "move",
    "bluetooth",
]  # FROMLIST: devcoredump: Add per device sysfs entry to enable/disable coredump
disp_overwrite["c43794b74082"] = [
    "move",
    "mm",
]  # CHROMIUM: Restrict swapon() to "zram" devices / lock down zram
disp_overwrite["dba4f3cbb765"] = [
    "move",
    "mm",
]  # CHROMIUM: mm: Optionally limit per-process reclaim.
disp_overwrite["b0d09d869ece"] = [
    "move",
    "other",
]  # UBUNTU: SAUCE: trace: add trace events for open(), exec() and uselib()
disp_overwrite["96b417ee494a"] = [
    "move",
    "arch",
]  # CHROMIUM: sched: Add /proc/pid/tasks/tid/latency_sensitive attribute
disp_overwrite["84c9494dc1c2"] = [
    "move",
    "arch",
]  # FIXUP: trace: sched: Use __get_wchan() instead of get_wchan()
disp_overwrite["58b9f94d66b0"] = [
    "move",
    "chromeos",
]  # CHROMIUM: ARM64: Add alt-syscall support
disp_overwrite["00e61e91369c"] = [
    "move",
    "chromeos",
]  # CHROMIUM: alt-syscall: Make required syscalls available for use
disp_overwrite["5ee58f274912"] = [
    "move",
    "gpu/other",
]  # CHROMIUM: config: mediatek: Enable Mali configs
disp_overwrite["26681b893753"] = [
    "move",
    "gpu/other",
]  # FROMGIT: accel/ivpu: Add IPC driver and JSM messages
disp_overwrite["8ca584bb62ee"] = [
    "move",
    "gpu/other",
]  # FROMGIT: accel/ivpu: Add PM support
disp_overwrite["93c50cc711b4"] = [
    "move",
    "gpu/other",
]  # FROMGIT: accel/ivpu: Fix spelling mistake "tansition" -> "transition"
disp_overwrite["82e42e181cc2"] = [
    "move",
    "gpu/other",
]  # FROMGIT: accel/ivpu: PM: remove broken ivpu_dbg() statements
disp_overwrite[
    "91a70c368104"
] = "drop"  # CHROMIUM: driver:  Support iwl7000 driver on v6.1
disp_overwrite[
    "4fe58164b6e0"
] = "drop"  # CHROMIUM: defconfig:  Support iwl7000 driver on v6.1
disp_overwrite[
    "2c618bec56d3"
] = "drop"  # CHROMIUM: ASoC: amd: acp: Add tdm support for codecs in machine driver
disp_overwrite[
    "2a50a5338af9"
] = "drop"  # FROMLIST: drm/bridge: add it6505 driver to read data-lanes and max-pixel-clock-khz from dt
disp_overwrite[
    "bd1096913a65"
] = "drop"  # FROMLIST: irqdomain: use per-domain mutex for associations
