# -*- coding: utf-8 -*-"
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Continuous rebase configuration file"""

rebase_baseline_branch = 'chromeos-5.15'
android_baseline_branch = 'deprecated/android-5.4'

# Set rebase_target to desired target.
# Select target tag, or 'latest' to rebase to ToT.
rebase_target = 'v5.14'

# Set rebasedb_name to None to use default.
# Otherwise pick desired file name.
rebasedb_name = f'rebase-{rebase_target}.db'

# Set datadir to None to use default.
# Otherwise provide absolute path name.
datadir = None

android_site = 'https://android.googlesource.com/'
kernel_site = 'https://git.kernel.org/'
chromium_site = 'https://chromium.googlesource.com/'

# Set to None if unused
android_repo = android_site + 'kernel/common'
next_repo = kernel_site + 'pub/scm/linux/kernel/git/next/linux-next'
upstream_repo = kernel_site + 'pub/scm/linux/kernel/git/torvalds/linux'
stable_repo = kernel_site + 'pub/scm/linux/kernel/git/stable/linux-stable'
chromeos_repo = chromium_site + 'chromiumos/third_party/kernel'

# Clear subject_droplist as follows to keep Android patches
# subject_droplist = []
subject_droplist = ['ANDROID:', 'Android:', 'android:']

# Control debug functionalities that are preferred to be disabled
# by default.
debug = False

# List of SHAs to be dropped manually, for example because they are
# upstream but not auto-detected by the tool.
sha_droplist = [
    ['9ab7893e57cd', 'upstream', '44758bafa536'],
    ['5482ed86293b', 'upstream', 'd30f370d3a49'],
    ['80269d1d18e8', 'upstream', '145d59baff59'],
    ['64096771a56d', 'upstream', 'b9b05664ebf6'],
    ['eff9d0917462', 'upstream', '93fe48a58590'],
    ['b716d03da4f7', 'upstream', 'f567ff6c76f7'],
    ['3e462e6b05e8', 'queued for v5.9', 'b56bdff78e0b'],
    ['f8f2b91749a2', 'queued for v5.9', 'bbcf90c0646a'],
]

droplist = [
    ('drivers/net/wireless/iwl7000', 'Intel'),
    ('drivers/gpu/drm/evdi', 'DisplayLink'),
    ('drivers/gpu/drm/i915', 'Intel'),
    ('drivers/gpu/drm/amd', 'AMD')
]

topiclist = [
    #     ['iwl7000', ['drivers/net/wireless/iwl7000']],
    ['chromeos',
     ['chromeos', 'COMMIT-QUEUE.ini', 'PRESUBMIT.cfg', 'init',
      'scripts',
      'include/linux/sched', 'kernel/sched',
      'drivers/tty/sysrq.c',
      'drivers/input', 'include/linux/input', 'kernel/cgroup',
      'drivers/hid',
      'security', 'include/linux/alt-syscall.h', 'include/linux/syscalls.h',
      'arch/arm64/kernel/alt-syscall.c',
      'arch/x86/kernel/alt-syscall.c', 'kernel/alt-syscall.ch',
      'kernel/futex.c',
      'include/linux/low-mem-notify.h', 'mm/low-mem-notify.c',
      'tools/mm/low-mem-test.c', 'drivers/char/mem.c',
      'mm', 'include/linux/mm_metrics.h', 'include/linux/swapops.h',
      'include/linux/mm.h', 'include/linux/nodemask.h', 'include/linux/cgroup.h',
      'mm/mm_init.c']],
    ['cros_ec',
     ['include/linux/platform_data/cros_ec_commands.h',
      'drivers/iio/common/cros_ec_sensors',
      'drivers/iio/accel/cros_ec_accel_legacy.c',
      'drivers/iio/pressure/cros_ec_baro.c',
      'drivers/iio/counter/cros_ec_sensors_sync.c',
      'drivers/iio/light/cros_ec_light_prox.c',
      'include/linux/iio/common/cros_ec_sensors_core.h',
      'drivers/platform/chrome/wilco_ec', 'drivers/rtc/rtc-wilco-ec',
      'drivers/power/supply/wilco-charger',
      'include/linux/platform_data/wilco-ec.h',
      'Documentation/ABI/testing/debugfs-wilco-ec',
      'Documentation/ABI/testing/sysfs-platform-wilco-ec',
      'drivers/extcon/extcon-usbc-cros_ec',
      'Documentation/devicetree/bindings/extcon/extcon-cros-ec.txt',
      'drivers/mfd/cros_ec', 'drivers/power/cros',
      'drivers/rtc/rtc-cros-ec', 'drivers/platform/chrome',
      'drivers/platform/x86/chrome', 'drivers/platform/arm/chrome',
      'drivers/input/keyboard/cros_ec',
      'drivers/power/supply/cros_usbpd-charger.c',
      'drivers/pwm/pwm-cros-ec.c',
      'drivers/regulator/cros_ec',
      'drivers/i2c/busses/i2c-cros-ec', 'include/linux/mfd/cros_ec',
      'include/linux/chromeos',
      'Documentation/devicetree/bindings/chrome',
      'drivers/iio', 'drivers/staging/iio', 'Documentation/driver-api/iio',
      'Documentation/devicetree/bindings/iio',
      'Documentation/devicetree/bindings/staging/iio',
      'Documentation/iio', 'include/linux/iio', 'include/uapi/linux/iio',
      'include/dt-bindings/iio']],
    ['power-thermal',
     ['drivers/power', 'drivers/base/power', 'kernel/power', 'drivers/opp',
      'include/dt-bindings/power', 'include/linux/power',
      'include/linux/pm', 'Documentation/power', 'arch/x86/power',
      'Documentation/devicetree/bindings/power',
      'Documentation/driver-api/thermal',
      'drivers/thermal', 'include/linux/thermal',
      'Documentation/devicetree/bindings/thermal',
      'drivers/firmware/google']],
    ['drm',
     ['include/drm/virtio_drm.h', 'include/uapi/drm/virtgpu_drm.h',
      'include/uapi/linux/virtio_gpu.h',
      'drivers/gpu/drm/amd', 'drivers/gpu/drm/i915', 'drivers/gpu/drm/mediatek',
      'drivers/gpu/drm/panel', 'drivers/gpu/drm/rockchip', 'drivers/gpu/drm/virtio',
      'drivers/gpu/drm', 'drivers/dma-buf']],
    ['gpu/other',
     ['drm', 'drivers/gpu', 'include/drm', 'Documentation/devicetree/bindings/drm',
      'include/uapi/drm']],
    ['media',
     ['drivers/media', 'drivers/staging/media',
      'include/media', 'include/uapi/linux/videodev2.h',
      'include/uapi/linux/v4l2-controls.h', 'Documentation/media',
      'include/uapi/linux/v4l2-common.h', 'Documentation/userspace-api/media']],
    ['bluetooth',
     ['net/bluetooth', 'drivers/bluetooth',
      'Documentation/devicetree/bindings/net/btusb.txt',
      'include/net/bluetooth']],
    ['net',
     ['drivers/net/usb', 'net', 'drivers/net', 'include/linux/tcp.h',
      'include/uapi/linux/tcp.h',
      'include/net', 'include/dt-bindings/net', 'include/linux/net',
      'include/uapi/linux/sockios.h',
      'include/uapi/linux/wireless.h',
      'include/uapi/nl80211-vnd-realtek.h',
      'Documentation/devicetree/bindings/net/wireless']],
    ['sound',
     ['sound', 'Documentation/devicetree/bindings/sound', 'include/sound',
      'include/uapi/sound']],
    ['block-fs',
     ['fs', 'include/linux/pstore',
      'Documentation/devicetree/bindings/reserved-memory/ramoops.txt',
      'Documentation/devicetree/bindings/misc/ramoops.txt',
      'Documentation/ramoops.txt',
      'block', 'drivers/md', 'init/do_mounts_dm.c', 'Documentation/device-mapper/boot.txt']],
    ['tpm-virtio',
     ['drivers/virtio', 'include/uapi/linux/virtwl.h',
      'drivers/char/tpm', 'Documentation/devicetree/bindings/security/tpm']],
    ['dts',
     ['arch/arm64/boot/dts/qcom',
      'arch/arm64/boot/dts/mediatek',
      'Documentation/devicetree/bindings/display/mediatek',
      'Documentation/devicetree/bindings/soc/mediatek',
      'Documentation/devicetree/bindings/arm/mediatek'
      'arch/arm64/boot/dts/rockchip', 'include/dt-bindings/clock/qcom,gpucc-sc7180.h',
      'arch/arm/boot/dts']],
    ['acpi',
     ['drivers/acpi']],
    ['arch',
     ['arch', 'kernel', 'lib', 'drivers/mfd', 'drivers/platform/x86', 'arch/x86',
      'arch/arm64/configs/chromiumos-container-vm-arm64_defconfig',
      'arch/x86/configs/chromiumos-container-vm-x86_64_defconfig',
      'arch/x86/configs/x86_64_arcvm_defconfig',
      'include/linux/mfd']],
    ['drivers',
     ['drivers', 'Documentation/mmc', 'include/linux/mmc',
      'include/uapi/linux/mmc']],
    ['devicetree',
     ['Documentation/devicetree']],
    ['other',
     ['tools/power/x86/turbostat', 'tools/testing/selftests/futex/functional']],
]

# We haven't found much use for topiclist_consolidated and topiclist_short
# due to a rather limited number of topics in the continuous rebase, hence
# these two are automatically generated to map topiclist 1:1
topiclist_consolidated = []
topiclist_short = []
for topic in topiclist:
    topic_name = topic[0]
    topiclist_consolidated.append([topic_name, [topic_name]])
    topiclist_short.append([topic_name, [topic_name]])
