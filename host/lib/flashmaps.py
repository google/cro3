# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Default flash maps for various boards we support.

These are used when no fdt is provided (e.g. upstream U-Boot with no fdt).
Each is a list of nodes.

Note: Use 'reg' instead of 'size' to fully specify the start and end of
each area, since there is no guarantee what order the nodes will appear
in the fdt, and if they are out of order the image will not boot.
"""

default_flashmaps = {
  'nyan' : [
    {
        'path' : '/flash',
        'reg' : [0, 0x400000],
    }, {
      'path' : '/flash/ro-boot',
      'label' : 'boot-stub',
      'size' : 512 << 10,
      'read-only' : True,
      'type' : 'blob signed',
      'required' : True
    }
  ],
  'daisy' : [
    {
        'path' : '/flash',
        'reg' : [0, 0x400000],
    }, {
        'path' : '/memory',
        'reg' : [0x40000000, 0x80000000],
    }, {
        'path' : '/iram',
        'reg' : [0x02020000, 384 << 10],
    }, {
        'path' : '/config',
        'samsung,bl1-offset' : 0x1400,
        'samsung,bl2-offset' : 0x3400,
        'u-boot-memory' : '/memory',
        'u-boot-offset' : [0x3e00000, 0x100000],
    }, {
        'path' : '/flash/pre-boot',
        'label' : "bl1 pre-boot",
        'reg' : [0, 0x2000],
        'read-only' : True,
        'filename' : "e5250.nbl1.bin",
        'type' : "blob exynos-bl1",
        'required' : True,
    }, {
        'path' : '/flash/spl',
        'label' : "bl2 spl",
        'reg' : [0x2000, 0x4000],
        'read-only' : True,
        'filename' : "bl2.bin",
        'type' : "blob exynos-bl2 boot,dtb",
        'payload' : '/flash/ro-boot',
        'required' : True,
    }, {
        'path' : '/flash/ro-boot',
        'label' : "u-boot",
        'reg' : [0x6000, 0x9a000],
        'read-only' : True,
        'type' : "blob boot,dtb",
        'required' : True,
    }
  ],
  'link' : [
    {
        'path' : '/flash',
        'reg' : [0, 0x800000],
    }, {
        'path' : '/flash/si-all',
        'label' : 'si-all',
        'reg' : [0x00000000, 0x00200000],
        'type' : 'ifd',
        'required' : True,
    }, {
        'path' : '/flash/ro-boot',
        'label' : 'boot-stub',
        'reg' : [0x00700000, 0x00100000],
        'read-only' : True,
        'type' : 'blob coreboot',
        'required' : True,
    }
  ],
  'peach' : [
    {
        'path' : '/flash',
        'reg' : [0, 0x400000],
    }, {
        'path' : '/memory',
        'reg' : [0x20000000, 0x80000000],     # Assume 2GB of RAM
    }, {
        'path' : '/iram',
        'reg' : [0x02020000, 384 << 10],
    }, {
        'path' : '/config',
        'samsung,bl1-offset' : 0x2400,
        'samsung,bl2-offset' : 0x4400,
        'u-boot-memory' : '/memory',
        'u-boot-offset' : [0x3e00000, 0x100000],
    }, {
        'path' : '/flash/pre-boot',
        'label' : "bl1 pre-boot",
        'reg' : [0, 0x2000],
        'read-only' : True,
        'filename' : "e5420.nbl1.bin",
        'type' : "blob exynos-bl1",
        'required' : True,
    }, {
        'path' : '/flash/spl',
        'label' : "bl2 spl",
        'reg' : [0x2000, 0x8000],
        'read-only' : True,
        'filename' : "bl2.bin",
        'type' : "blob exynos-bl2 boot,dtb",
        'payload' : '/flash/ro-boot',
        'required' : True,
    }, {
        'path' : '/flash/ro-boot',
        'label' : "u-boot",
        'reg' : [0xa000, 0x9a000],
        'read-only' : True,
        'type' : "blob boot,dtb",
        'required' : True,
    }
  ],
}
