# -*- coding: utf-8 -*-"
# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Configuration file"""

rebase_baseline_branch = 'chromeos-5.10'
android_baseline_branch = 'android13-5.10'

# Set rebase_target to desired target.
# Select target tag, or 'latest' to rebase to ToT.
rebase_target = 'latest'

# Set rebasedb_name to None to use default.
# Otherwise pick desired file name.
rebasedb_name = None

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
]

droplist = [
    ('drivers/net/wireless/iwl7000', 'Intel'),
    #           ('drivers/gpu/drm/i915', 'Intel'),
    #           ('drivers/gpu/drm/amd', 'AMD')
]

topiclist = [['chromeos',
      ['chromeos', 'COMMIT-QUEUE.ini', 'PRESUBMIT.cfg']],
     ['cros_ec/iio',
      ['drivers/iio/common/cros_ec_sensors',
       'drivers/iio/accel/cros_ec_accel_legacy.c',
       'drivers/iio/pressure/cros_ec_baro.c',
       'drivers/iio/counter/cros_ec_sensors_sync.c',
       'drivers/iio/light/cros_ec_light_prox.c',
       'include/linux/iio/common/cros_ec_sensors_core.h',
       'Documentation/ABI/testing/sysfs-bus-iio-cros-ec'
       ]],
     ['cros_ec/wilco',
      ['drivers/platform/chrome/wilco_ec', 'drivers/rtc/rtc-wilco-ec',
      'drivers/power/supply/wilco-charger',
      'include/linux/platform_data/wilco-ec.h',
      'Documentation/ABI/testing/debugfs-wilco-ec',
      'Documentation/ABI/testing/sysfs-platform-wilco-ec']],
     ['cros_ec/extcon',
      ['drivers/extcon/extcon-usbc-cros_ec',
       'drivers/extcon/extcon-tcss-cros-ec.c',
       'drivers/extcon/extcon-tcss-cros-ec.h',
       'Documentation/devicetree/bindings/extcon/extcon-cros-ec.txt'
      ]],
     ['cros_ec',
      ['drivers/mfd/cros_ec', 'drivers/power/cros',
       'drivers/rtc/rtc-cros-ec', 'drivers/platform/chrome',
       'drivers/platform/x86/chrome', 'drivers/platform/arm/chrome',
       'drivers/input/keyboard/cros_ec',
       'drivers/power/supply/cros_usbpd-charger.c',
       'drivers/pwm/pwm-cros-ec.c',
       'drivers/regulator/cros_ec',
       'drivers/i2c/busses/i2c-cros-ec', 'include/linux/mfd/cros_ec',
       'include/linux/chromeos',
       'include/linux/platform_data/cros_ec_commands.h',
       'sound/soc/codecs/cros_ec_codec.c',
       'Documentation/devicetree/bindings/chrome',
       'Documentation/ABI/testing/sysfs-class-chromeos-driver-cros-ec-vbc'
       'Documentation/ABI/testing/debugfs-cros-ec'
       ]],
     ['power',
      ['drivers/power', 'drivers/base/power', 'kernel/power', 'drivers/opp',
       'include/dt-bindings/power', 'include/linux/power',
       'include/linux/pm', 'Documentation/power', 'arch/x86/power',
       'Documentation/devicetree/bindings/power']],
     ['usb-gadget',
      ['drivers/usb/gadget']],
     ['usb',
      ['drivers/usb', 'include/linux/usb', 'include/uapi/linux/usb',
       'Documentation/devicetree/bindings/usb',
       'tools/usb']],
     ['arm/mali',
      ['drivers/gpu/arm']],
     ['drm/amd',
      ['drivers/gpu/drm/amd']],
     ['drm/i915',
      ['drivers/gpu/drm/i915']],
     ['drm/mediatek',
      ['drivers/gpu/drm/mediatek']],
     ['drm/qualcomm',
      ['drivers/gpu/drm/msm']],
     ['drm/panel',
      ['drivers/gpu/drm/panel']],
     ['drm/rockchip',
      ['drivers/gpu/drm/rockchip']],
     ['drm/virtio',
      ['drivers/gpu/drm/virtio', 'include/drm/virtio_drm.h',
       'include/uapi/drm/virtgpu_drm.h', 'include/uapi/linux/virtio_gpu.h']],
     ['gpu/other',
      ['drm', 'drivers/gpu', 'include/drm', 'Documentation/devicetree/bindings/drm',
       'include/uapi/drm']],
     ['media/qcom',
      ['drivers/media/platform/qcom',
       'Documentation/devicetree/bindings/media/qcom,sc7180-venus.yaml',
       'Documentation/devicetree/bindings/media/qcom,sdm845-venus.yaml',
       'Documentation/devicetree/bindings/media/qcom,msm8916-venus.yaml',
       'Documentation/devicetree/bindings/media/qcom,msm8996-venus.yaml',
       'Documentation/devicetree/bindings/media/qcom,sdm845-venus-v2.yaml',
       'Documentation/devicetree/bindings/media/qcom,venus.txt']],
     ['media/virtio',
      ['drivers/media/virtio']],
     ['media/other',
      ['drivers/media', 'drivers/staging/media',
       'include/media', 'include/uapi/linux/videodev2.h',
       'include/uapi/linux/v4l2-controls.h', 'Documentation/media',
       'Documentation/devicetree/bindings/media']],
     ['video',
      ['drivers/video']],
     ['input',
      ['drivers/input', 'include/linux/input']],
     ['iio',
      ['drivers/iio', 'drivers/staging/iio', 'Documentation/driver-api/iio',
       'Documentation/devicetree/bindings/iio',
       'Documentation/devicetree/bindings/staging/iio',
       'Documentation/iio', 'include/linux/iio', 'include/uapi/linux/iio',
       'include/dt-bindings/iio']],
     ['mmc',
      ['drivers/mmc', 'Documentation/mmc', 'include/linux/mmc',
       'include/uapi/linux/mmc']],
     ['mtd',
      ['drivers/mtd', 'include/linux/mtd', 'include/uapi/mtd',
       'Documentation/mtd', 'Documentation/devicetree/bindings/mtd']],
     ['bluetooth',
      ['net/bluetooth', 'drivers/bluetooth',
       'Documentation/devicetree/bindings/net/btusb.txt',
       'include/net/bluetooth']],
     ['wireless',
      ['net/wireless', 'drivers/net/wireless',
       'include/uapi/linux/wireless.h',
       'include/uapi/nl80211-vnd-realtek.h',
       'Documentation/devicetree/bindings/net/wireless']],
     ['net',
      ['drivers/net/usb', 'net', 'drivers/net', 'include/linux/tcp.h',
       'include/uapi/linux/tcp.h',
       'include/net', 'include/dt-bindings/net', 'include/linux/net',
       'include/uapi/linux/sockios.h']],
     ['sound/intel',
      ['sound/soc/intel', 'sound/soc/sof/intel']],
     ['sound/other',
      ['sound', 'Documentation/devicetree/bindings/sound', 'include/sound',
       'include/uapi/sound']],
     ['security',
      ['security', 'include/linux/alt-syscall.h', 'include/linux/syscalls.h',
       'arch/arm64/kernel/alt-syscall.c',
       'arch/x86/kernel/alt-syscall.c', 'kernel/alt-syscall.ch']],
     ['android',
      ['android', 'Documentation/android', 'drivers/android',
       'drivers/staging/android',
       'include/linux/android', 'include/uapi/linux/android']],
     ['fs/ecryptfs',
      ['fs/ecryptfs']],
     ['fs/esdfs',
      ['fs/esdfs']],
     ['fs/other',
      ['fs']],
     ['hid',
      ['drivers/hid']],
     ['md',
      ['drivers/md', 'init/do_mounts_dm.c', 'Documentation/device-mapper/boot.txt']],
     ['thermal',
      ['drivers/thermal', 'include/linux/thermal',
       'Documentation/devicetree/bindings/thermal']],
     ['scsi',
      ['drivers/scsi']],
     ['virtio',
      ['drivers/virtio', 'include/uapi/linux/virtwl.h']],
     ['sysrq',
      ['drivers/tty/sysrq.c']],
     ['firmware/google',
      ['drivers/firmware/google']],
     ['tpm',
      ['drivers/char/tpm', 'Documentation/devicetree/bindings/security/tpm']],
     ['lowmem',
      ['include/linux/low-mem-notify.h', 'mm/low-mem-notify.c',
       'tools/mm/low-mem-test.c', 'drivers/char/mem.c']],
     ['mm',
      ['mm', 'include/linux/mm_metrics.h', 'include/linux/swapops.h']],
     ['scheduler',
      ['include/linux/sched', 'kernel/sched']],
     ['cgroup',
      ['kernel/cgroup']],
     ['dts/qcom',
      ['arch/arm64/boot/dts/qcom']],
     ['dts/mediatek',
      ['arch/arm64/boot/dts/mediatek',
       'Documentation/devicetree/bindings/display/mediatek',
       'Documentation/devicetree/bindings/soc/mediatek',
       'Documentation/devicetree/bindings/arm/mediatek'
      ]],
     ['acpi',
      ['drivers/acpi']],
     ['arcvm/container',
      ['arch/arm64/configs/chromiumos-container-vm-arm64_defconfig',
       'arch/x86/configs/chromiumos-container-vm-x86_64_defconfig',
       'arch/x86/configs/chromiumos-jail-vm-x86_64_defconfig',
       'arch/x86/configs/x86_64_arcvm_defconfig',
       'arch/arm64/configs/arm64_arcvm_defconfig']],
     ['cpufreq',
      ['drivers/cpufreq']],
     ['iommu',
      ['drivers/iommu']],
     ['soundwire',
      ['drivers/soundwire', 'include/linux/soundwire']],
     ['remoteproc',
      ['drivers/remoteproc', 'drivers/rpmsg', 'include/linux/rpmsg']],
     ['mfd',
      ['drivers/mfd']],
     ['drivers/soc',
      ['drivers/soc', 'include/linux/soc']],
     ['arch/arm64',
      ['arch/arm64']],
     ['arch/arm',
      ['arch/arm']],
     ['arch/x86',
      ['arch/x86', 'drivers/platform/x86']],
     ['devicetree',
      ['Documentation/devicetree']],
     ['block',
      ['block']],
     ['kernel',
      ['kernel']],
     ['drivers',
      ['drivers']],
     ['tools',
      ['tools']],
     ['other',
      ['lib', 'scripts', 'init']],
    ]

topiclist_consolidated = [
    ['cros_ec', ['cros_ec/iio', 'cros_ec/wilco', 'cros_ec/extcon', 'cros_ec']],
    [
        'drm',
        [
            'drm/amd', 'drm/i915', 'drm/mediatek', 'drm/qualcomm', 'drm/panel',
            'drm/rockchip', 'gpu/other', 'arm/mali'
        ]
    ],
    [
        'virtio',
        ['drm/virtio', 'virtio', 'media/virtio', 'virt/kvm', 'arcvm/container']
    ],
    [
        'other',
        [
            'other', 'devicetree', 'acpi', 'cpufreq', 'firmware/google',
            'devfreq', 'block', 'android', 'video', 'sysrq', 'scheduler',
            'tools'
        ]
    ],
    ['dts', ['dts/arm', 'dts/qcom', 'dts/mediatek', 'dts/rk3399']],
    [
        'drivers',
        [
            'drivers', 'iio', 'input', 'usb', 'usb-gadget', 'mmc', 'mtd',
            'drivers/mediatek', 'drivers/rockchip', 'iommu', 'mfd',
            'remoteproc', 'devfreq', 'regulator', 'scsi', 'soundwire'
        ]
    ],
    [
        'sound',
        ['sound/intel', 'sound/other', 'sound/mediatek', 'sound/rockchip']
    ],
    ['media', ['media/qcom', 'media/other' ]],
    ['mm', ['cgroup', 'lowmem', 'mm']],
    ['arch', ['arch/x86', 'arch/arm64', 'arch/arm']],
    ['fs', ['fs/pstore', 'fs/ecryptfs', 'fs/other']],
    ['net', ['wireless', 'net']],
]
