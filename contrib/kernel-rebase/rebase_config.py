# Commits to revert on each topic branch *before* topic fixups
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Parts of the file are automatically generated
# pylint: disable=line-too-long

"""automatic rebase-specific data"""

import hooks # pylint: disable=unused-import

verify_board = 'caroline'
verify_package = 'chromeos-kernel-upstream'

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

topic_fixups['bluetooth'] = [
    'Handle BR&ADR devices during suspend'
]
topic_fixups['cros_ec'] = [
    'Revert "iio: cros_ec: unify hw fifo attributes into the core file"'
]
topic_fixups['block-fs'] = [
    'add ChromeOS specific platform functions',
    'bring over dm-verity-chromeos.c',
    'update ESDFS to use changed FS API'
]
topic_fixups['net'] = [
    'Introduce ANDROID_PARANOID_NETWORK as per-netns setting'
]
topic_fixups['drm'] = [
    'Add drm_main_relax debugfs file (non-root set&drop main ioctls)',
    'Add an API for exporting sync files (v12)',
    'Track context current active time'
]

topic_fixups['chromeos'] = [
    'Restrict swapon() to "zram" devices lock down zram'
]

topic_fixups['media'] = [
    'add a quirk for ROI fixup'
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
    'process fput task_work with TWA_SIGNAL'
]

# cherry-pick a list of patches before a given patch
# during automatic rebase.
# example:
# patch_deps = {
#     '0d022b4a1e19': ['6e18e51a1c19']
# }
patch_deps = {
    '0d022b4a1e19': ['6e18e51a1c19'],
    '03ee1420ddff': ['13f1f28be1c3'],
    '5f46e9f6605b': ['fbfe1e70219a']
}

# Add entry here to overwrite default disposition on particular commit
# WARNING: lines can be automatically appended here when user chooses
# to drop the commit from rebase script.
disp_overlay = {}
# example
# disp_overlay['62b865c66db4'] = 'drop'

# ANDROID: export security_path_chown
disp_overlay['69513bac7694'] = 'pick'
# ANDROID: Revert "fs: unexport vfs_read and vfs_write"
disp_overlay['d440e09ca08e'] = 'pick'

# FROMLIST: scsi: ufs: clear UAC for FFU
disp_overlay['62b865c66db4'] = 'drop'
# FROMLIST: scsi: ufs: clear uac for rpmb lun
disp_overlay['848c22dc91a2'] = 'drop'
# FROMLIST: ASoC: Intel: Skylake: Check the kcontrol against NULL
disp_overlay['034bbd4fcf91'] = 'drop'
# FROMGIT: thermal: Add sysfs binding for cooling device and thermal zone
disp_overlay['6465ae0d5434'] = 'drop'
# FROMGIT: thermal: Make cooling device trip point writable from sysfs
disp_overlay['52eec2d9a503'] = 'drop'
# FROMGIT: docs: thermal: Add bind, unbind information together with trip point
disp_overlay['d580b4726a07'] = 'drop'
# CHROMIUM: chromeos/config: x86_64: enable IWL7000 driver
disp_overlay['95264726f564'] = 'drop'
# UPSTREAM: Bluetooth: Update Adv monitor count upon removal
disp_overlay['da39575e3231'] = 'drop'
# CHROMIUM: FIXUP: Ensure iwl7000 is configurable
disp_overlay['22592d5eb58a'] = 'drop'
disp_overlay['7fd8e1354568'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180: Add node for ALSA sound card registration
disp_overlay['b530b50b9ce1'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180-trogdor: Fix sc7180 sound card dtsi for new properties
disp_overlay['d804813827b2'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180-pompom shouldn't inherit trogdor-r1
disp_overlay['3835fb2d791b'] = 'drop' # CHROMIUM: arm64: dts: qcom: Disable type-c port on pompom
disp_overlay['348093d7727e'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180-trodgor: Fix pinmux usage
disp_overlay['65d2db6c59be'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180-trogdor: Fix sound card node
disp_overlay['ca1e6a3327e2'] = 'drop' # CHROMIUM: arm64: dts: qcom: Add label for sound node
disp_overlay['cca26f9d2a69'] = 'drop' # CHROMIUM: arm64: dts: qcom: Use proper compatible string for pompom sound card
disp_overlay['07bf0dd20b92'] = 'drop' # CHROMIUM: arm64: qcom: sc7180: trogdor: Add ADC nodes and thermal zone for 5v-choke thermistor on pompom
disp_overlay['909d76004976'] = 'drop' # CHROMIUM: arm64: dts: qcom: Limit camera clk driver to CoachZ
disp_overlay['ab4093247700'] = 'drop' # CHROMIUM: arm64: dts: qcom: trogdor: Change compatible string and model
disp_overlay['2f9d5f9b44d0'] = 'drop' # CHROMIUM: arm64: dts: qcom: Add adau7002 support for coachz
disp_overlay['e0c3be8f6bce'] = 'drop' # CHROMIUM: arm64: dts: qcom: trogdor: Remove p sensor on pompom
disp_overlay['9e8322de64ff'] = 'drop' # CHROMIUM: arm64: dts: qcom: trogdor: Configure Pen insert/ eject behavior
disp_overlay['655eda0af8b1'] = 'drop' # FROMLIST: Asoc: qcom: dts: Update iommu property for simultaneous playback
disp_overlay['b59888aefd1e'] = 'drop' # CHROMIUM: arm64: dts: qcom: Set the DMIC clock driving on Pompom
disp_overlay['bd92cf75dcd6'] = 'drop' # CHROMIUM: arm64: dts: qcom: Reorganize CoachZ to follow others
disp_overlay['978425278754'] = 'drop' # CHROMIUM: arm64: qcom: sc7180: trogdor: Fix order of phandle section for pompom
disp_overlay['2c7ca6d9cdd9'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180: trogdor: Add 'regulator-boot-on' for pp3300-hub
disp_overlay['30bc87298a7d'] = 'drop' # UPSTREAM: PCI: Export pci_rebar_get_possible_sizes()
disp_overlay['e2ea9fbe51a6'] = 'drop' # CHROMIUM: sched: Add /proc/pid/tasks/tid/latency_sensitive attribute
disp_overlay['6a7fb9b5b83c'] = 'drop' # UPSTREAM: drm/amdgpu/display: remove an old DCN3 guard
disp_overlay['724f9f609a79'] = 'drop' # UPSTREAM: drm/amdgpu/display: fix warning when CONFIG_DRM_AMD_DC_DCN is not defined
disp_overlay['e9d9d548fc0a'] = 'drop' # UPSTREAM: drm/amdgpu/display: fix build when CONFIG_DRM_AMD_DC_DCN is not defined
disp_overlay['da23336459fb'] = 'drop' # FROMLIST: arm64: dts: mt8183-kukui: Enable thermal Tboard
disp_overlay['3b69b8a1515a'] = 'drop' # Revert "FROMLIST: Bluetooth: Update Adv monitor count upon removal"
disp_overlay['c5d00cc3779e'] = 'drop' # FROMLIST: media: mtk-vcodec: Use pm_runtime_resume_and_get for PM get_sync
disp_overlay['13047d2b9924'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180: Disable skin temperature thermal zone for coachz
disp_overlay['8de0f20fc570'] = 'drop' # FIXUP: FROMLIST: sched: Add a coresched command line option
disp_overlay['588857db26e5'] = 'drop' # CHROMIUM: iommu/intel: Specialcase for internal but untrusted devices
disp_overlay['be3ed1509047'] = 'drop' # BACKPORT: FROMLIST: Bluetooth: adding BTUSB_VALID_LE_STATES to Intel Controllers
disp_overlay['cd28f80e98d9'] = 'drop' # CHROMIUM: Bluetooth: remove an unused variable
disp_overlay['fbfe1e70219a'] = 'drop' # FROMLIST: KVM: mmu: introduce new gfn_to_pfn_page functions
disp_overlay['cd6529601dd1'] = 'drop' # CHROMIUM: arm64: dts: qcom: Add dts files for sc7180-trogdor-pompom
disp_overlay['ccbd9a486631'] = 'drop' # CHROMIUM: arm64: dts: qcom: Use proper compatible string for pompom display
disp_overlay['b2b08a5af157'] = 'drop' # CHROMIUM: arm64: dts: qcom: Enable i2c-5 and Enable Proximity Sensor SX9311
disp_overlay['9424e235b405'] = 'drop' # CHROMIUM: arm64: dts: qcom: Add sc7180-pompom-r1
disp_overlay['19391e9e1530'] = 'drop' # CHROMIUM: arm64: dts: qcom: Add sc7180-coachz
disp_overlay['bf616126dbfa'] = 'drop' # CHROMIUM: arm64: dts: qcom: PWM for backlight is 0 on CoachZ
disp_overlay['9b8671768cd8'] = 'drop' # CHROMIUM: arm64: dts: qcom: Only enable p-sensor on Lazor LTE SKUs
disp_overlay['3580d48018ee'] = 'drop' # CHROMIUM: arm64: dts: qcom: Fix sc7180-trogdor-coachz eDP lanes
disp_overlay['3107a86ed003'] = 'drop' # CHROMIUM: arm64: dts: qcom: Make sc7180-trogdor-coachz touchscreen probe
disp_overlay['d86814edd5b2'] = 'drop' # CHROMIUM: arm64: dts: qcom: Only enable i2c5 on devices that use it
disp_overlay['21418d69d435'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180: Keep using pp3300_l7c as supply for pp3300_hub for trogdor r0
disp_overlay['34bc46a113fa'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180: Add sc7180-pompom-r2
disp_overlay['a0100a25c161'] = 'drop' # CHROMIUM: arm64: dts: qcom: Remove prox sensor on Limozeen
disp_overlay['0383da3aca29'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180: Enable vivaldi keyboard for pompom
disp_overlay['a49b8bb6e63d'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180: remove dmic_clk_en
disp_overlay['3de4e6ccf396'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180: add dmic_clk_en back
disp_overlay['c5876158d1f8'] = 'drop' # CHROMIUM: arm64: dts: qcom: Add cros ec proximity on CoachZ
disp_overlay['2c4ec85e9ebe'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180: Clean up audio dts to match upstream
disp_overlay['3677513fffa0'] = 'drop' # CHROMIUM: arm64: dts: qcom: Remove "dmic_clk_en" from coachz revs
disp_overlay['c8e36674ea80'] = 'drop' # CHROMIUM: arm64: dts: qcom: sc7180: Update trogdor for new dp node label
disp_overlay['2f51beb00a6d'] = 'drop' # CHROMIUM: arm64: dts: qcom: Add trogdor-r2
disp_overlay['678d6b8fbf75'] = 'drop' # CHROMIUM: arm64: dts: qcom: Fix lane polarities on trogdor-r2
disp_overlay['3e7cf116596c'] = 'drop' # FROMLIST: drm/mediatek: clear pending flag when cmdq packet is done.
disp_overlay['0c4975c2f2fe'] = 'drop' # FROMLIST: drm/i915/adlp: Define GuC/HuC for Alderlake_P
disp_overlay['65f77de7444e'] = 'drop' # FROMLIST: pwm: fine tune pwm-mtk-disp clock control flow
disp_overlay['98583bf3ca78'] = 'drop' # FROMLIST: pwm/mtk_disp: fix update reg issue when chip doesn't have commit
disp_overlay['6adf7ed211c8'] = 'drop' # FROMLIST: usb: xhci-mtk: handle bandwidth table rollover
disp_overlay['e2052fb234bb'] = 'drop' # CHROMIUM: arm64: dts: qcom: Fix trackpad on sc7180-trogdor-lazor-limozeen-rev4-sku5
