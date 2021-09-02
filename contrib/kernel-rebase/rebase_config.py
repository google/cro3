# Commits to revert on each topic branch *before* topic fixups
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Parts of the file are automatically generated
# pylint: disable=line-too-long

"""automatic rebase-specific data"""

global_reverts = []

topic_fixups = {}
# example:
# topic_fixups['bluetooth'] = ['fd83ec5d9b94']

topic_fixups['bluetooth'] = [
    'fd83ec5d9b94'
]
topic_fixups['cros_ec'] = [
    'f28f6f7055a6'
]
topic_fixups['block-fs'] = [
    'cb90fca27f47',
    '3f91858b76dd',
    '009fc62cede0',
    '08c17be52b99',
    'f6a790778992',
    'e5d3ba38d64d'
]
topic_fixups['net'] = [
    '9bf5655f0eea'
]
topic_fixups['drm'] = [
    '56356fd6f922',
    '7936d45c60ff'
]

topic_fixups['chromeos'] = [
    '0f7cd1316628', # FIXUP: BACKPORT: FROMLIST: mm: multigenerational lru: eviction
    '2ccc00ec1edd'  # FIXUP: BACKPORT: FROMLIST: mm: multigenerational lru: aging
]

topic_fixups['dts'] = [
    '16a45bcf03d2' # FIXUP: arm64: dts: qcom: Add sc7180-trogdor-coachz skus
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
    'e0783589ae58'
]

# cherry-pick a list of patches before a given patch
# during automatic rebase.
# example:
# patch_deps = {
#     '0d022b4a1e19': ['6e18e51a1c19']
# }
patch_deps = {
    '0d022b4a1e19': ['6e18e51a1c19'],
    '03ee1420ddff': ['13f1f28be1c3']
}

# Add entry here to overwrite default disposition on particular commit
# WARNING: lines can be automatically appended here when user chooses
# to drop the commit from rebase script.
disp_overlay = {}
# example
# disp_overlay['62b865c66db4'] = 'drop'

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
