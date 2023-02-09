# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Config for icetower v3"""

PACS = [
    # addr:ch  name                 nom         rsense
    ("0x10:0", "PPVAR_MCU", 3.300, 0.5),  # R1
    ("0x10:1", "PPVAR_FP", 3.300, 0.5),  # R10
    ("0x10:2", "PP3300_FP", 3.300, 0.5),  # R875
    ("0x10:3", "PP1800_FP", 1.800, 0.5),  # R911
]

RAILS = []

GPIOS = []
