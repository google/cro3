# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""INA2XX register information"""

CONF = 0x00
VSHUNT1 = 0x01
VBUS1 = 0x02
POWER = 0x03
CURRENT = 0x04
CALIBRATION = 0x05
MASK = 0x06
ALERTLIM = 0x0F

"""
Configuration register information
"""
# CH_SHIFT is only for INA3221 comptability
CH_SHIFT = 12
AVG_SHIFT = 9
VBUS_CT_SHIFT = 6
VSHUNT_CT_SHIFT = 3
MODE_SHIFT = 0
RESET = 1 << 15

# Averaging options
AVG = {1: 0, 4: 1, 16: 2, 64: 3, 128: 4, 256: 5, 512: 6, 1024: 7}

# VBUS and VSHUNT CT in micro seconds
CT = {140: 0, 204: 1, 332: 2, 588: 3, 1100: 4, 2116: 5, 4156: 6, 8244: 7}

""" Constants """
VSHUNT_SCALE = 2.5e-6
VBUS_SCALE = 1.25e-3
CVRF_MASK = 0x8
