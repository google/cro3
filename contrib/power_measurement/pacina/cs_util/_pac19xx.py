# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""PAC193x and PAC195x register information"""

import cs_types

FSR = 0.1
FSV = 32
V_POLAR = {
    cs_types.Polarity.UNIPOLAR: 2**16,
    cs_types.Polarity.BIPOLAR: 2**15,
}
P_POLAR_195x = {
    cs_types.Polarity.UNIPOLAR: 2**30,
    cs_types.Polarity.BIPOLAR: 2**29,
}
P_POLAR_193x = {
    cs_types.Polarity.UNIPOLAR: 2**28,
    cs_types.Polarity.BIPOLAR: 2**27,
}
"""pac_registers of the PAC19xx"""
REFRESH = 0x00
REFRESH_G = 0x1E
CTRL = 0x01
ACC_COUNT = 0x02
VACC1 = 0x03
VACC2 = 0x04
VACC3 = 0x05
VACC4 = 0x06
VBUS1 = 0x07
VBUS2 = 0x08
VBUS3 = 0x09
VBUS4 = 0x0A
VSENSE1 = 0x0B
VSENSE2 = 0x0C
VSENSE3 = 0x0D
VSENSE4 = 0x0E
VBUS1_AVG = 0x0F
VBUS2_AVG = 0x10
VBUS3_AVG = 0x11
VBUS4_AVG = 0x12
VSENSE1_AVG = 0x13
VSENSE2_AVG = 0x14
VSENSE3_AVG = 0x15
VSENSE4_AVG = 0x16
VPOWER1 = 0x17
VPOWER2 = 0x18
VPOWER3 = 0x19
VPOWER4 = 0x1A
SMBUS_SET = 0x1C
NEG_PWR_FSR = 0x1D
REFRESH_G = 0x1E
REFRESH_V = 0x1F
SLOW = 0x20
CTRL_ACT = 0x21
NEG_PWR_FSR_ACT = 0x22
CTRL_LAT = 0x23
NEG_PWR_FSR_LAT = 0x24
ACCUM_CONF = 0x25
ALERT_STATUS = 0x26
SLOW_ALERT1 = 0x27
GPIO_ALERT2 = 0x28
ACC_FULL_LIM = 0x29
OC_LIM1 = 0x30
OC_LIM2 = 0x31
OC_LIM3 = 0x32
OC_LIM4 = 0x33
UC_LIM1 = 0x34
UC_LIM2 = 0x35
UC_LIM3 = 0x36
UC_LIM4 = 0x37
OP_LIM1 = 0x38
OP_LIM2 = 0x39
OP_LIM3 = 0x3A
OP_LIM4 = 0x3B
OV_LIM1 = 0x3C
OV_LIM2 = 0x3D
OV_LIM3 = 0x3E
OV_LIM4 = 0x3F
UV_LIM1 = 0x40
UV_LIM2 = 0x41
UV_LIM3 = 0x42
UV_LIM4 = 0x43
OC_LIM1_NSAMP = 0x44
UC_LIM1_NSAMP = 0x45
OP_LIM1_NSAMP = 0x46
OV_LIM1_NSAMP = 0x47
UV_LIM1_NSAMP = 0x48
ALERT_ENABLE = 0x49
ACC_CONF_ACT = 0x4A
ACC_CONF_LAT = 0x4B
PRODUCT_ID = 0xFD
MANUFACTURER_ID = 0xFE
REVISION_ID = 0xFF
