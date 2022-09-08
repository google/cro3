# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Config for rex r0"""

PACS = [
    # addr:ch  name                 nom         rsense
    ('0x10:0', 'PP0770_SOC_IN',     0.770,      0.01),#R380
    ('0x10:1', 'PPVAR_VCCSA_IN',    0.000,      0.01),#R379
    ('0x10:2', 'PP1250_SOC',        1.250,      0.01),#R875
    ('0x10:3', 'PP0770_SOC',        0.770,      0.01),#R911

    ('0x11:0', 'PP1065_MEM',        1.065,      0.003),#R398
    ('0x11:1', 'PP1800_MEM',        1.800,      0.01),#RS2
    ('0x11:2', 'PP1800_S5',         1.800,      0.003),#R866
    ('0x11:3', 'PP0500_MEM_S3',     0.500,      0.001),#R874

    ('0x12:0', 'PPVAR_VCCCORE_PH1', 0.000,      0.01),#R906
    ('0x12:1', 'PP3300_S5',         3.300,      0.005),#R590
    ('0x12:2', 'PP3300_Z5',         3.300,      0.01),#R1085
    ('0x12:3', 'PP5000_Z1',         5.000,      0.005),#R591

    ('0x13:0', 'PP3300_FCAM_X',     3.300,      0.01),#R58
    ('0x13:1', 'PP3300_HPS_X',      3.300,      0.01),#R59
    ('0x13:2', 'PP3300_EDP_X',      3.300,      0.02),#R657
    ('0x13:3', 'PP3300_TCHSCR_X',   3.300,      0.02),#R658

    ('0x14:0', 'PP1800_EC_Z1',      1.800,      0.01),#R699
    ('0x14:1', 'PPVAR_VCCGT_IN',    0.000,      0.01),#R378
    ('0x14:2', 'PP3300_Z1',         3.300,      0.1),#R553
    ('0x14:3', 'PP3300_EC_Z1',      3.300,      0.01),#R700

    ('0x15:0', 'PP1800_FP_X',       1.800,      0.5),#R124
    ('0x15:1', 'PP3300_FP_X',       3.300,      0.5),#R123
    ('0x15:2', 'PP5000_TCHPAD_X',   5.000,      0.01),#R16
    ('0x15:3', 'PPVAR_VCCCORE_PH2', 0.000,      0.01),#R908

    ('0x16:0', 'PP3300_WWAN_X',     3.300,      0.005),#R235
    ('0x16:1', 'PP3300_GSC_Z1',     3.300,      0.01),#R415
    ('0x16:2', 'PP3300_SSD_X',      3.300,      0.005),#R236
    ('0x16:3', 'PP3300_HDMI_X',     3.300,      0.02),#R679

    ('0x17:0', 'PP3300_WLAN_X',     3.300,      0.01),#R873
    ('0x17:1', 'PP1800_GSC_Z1',     1.800,      0.01),#R414
    ('0x17:2', 'PP1500_RTC_Z5',     1.500,      0.5),#R832
    ('0x17:3', 'PP5000_HDMI_X',     5.000,      0.01),#R695

    ('0x18:0', 'PP3300_SD',         3.300,      0.01),#R143
    ('0x18:1', 'PPVAR_SYS_SD',      0.000,      0.01),#R144
    ('0x18:2', 'PPVAR_VBUS_IN',     0.000,      0.001),#R904
    ('0x18:3', 'PP5000_FAN',        5.000,      0.01),#R939

    ('0x19:0', 'PPVAR_SYS',         0.000,      0.001),#R905
    ('0x19:1', 'PPVAR_VCCCORE_PH3', 0.000,      0.01),#R907
    ('0x19:2', 'PPVAR_VCCSA',       0.000,      0.01),#R912
    ('0x19:3', 'PPVAR_VCCCORE_IN',  0.000,      0.01),#R399

    ('0x1A:0', 'PPVAR_VCCGT_PH2',   0.000,      0.01),#R910
    ('0x1A:1', 'PP3300_TCHPAD_X',   3.300,      0.02),#R15
    ('0x1A:2', 'PPVAR_VCCGT_PH1',   0.000,      0.01),#R909
    ('0x1A:3', 'PP1250_SOC_IN',     1.250,      0.025),#R448
]

RAILS = [
    # rail           parent
    ('PP0770_SOC_IN','PPVAR_SYS'),
    ('PPVAR_VCCSA_IN','PPVAR_SYS'),
    ('PP1250_SOC','PPVAR_SYS'),
    ('PP0770_SOC','PPVAR_SYS'),
    ('PP1065_MEM','PPVAR_SYS'),
    ('PP1800_MEM','PP5000_Z1'),
    ('PP1800_S5','PPVAR_SYS'),
    ('PP0500_MEM_S3','PP1065_MEM_S3'),
    ('PPVAR_VCCCORE_PH1','PPVAR_VCCCORE_IN'),
    ('PP3300_S5','PPVAR_SYS'),
    ('PP3300_Z5','PPVAR_SYS'),
    ('PP5000_Z1','PPVAR_SYS'),
    ('PP3300_FCAM_X','PP3300_S5'),
    ('PP3300_HPS_X','PP3300_S5'),
    ('PP3300_EDP_X','PP3300_S5'),
    ('PP3300_TCHSCR_X','PP3300_S5'),
    ('PP1800_EC_Z1','PP1800_Z1'),
    ('PPVAR_VCCGT_IN','PPVAR_SYS'),
    ('PP3300_Z1','PP3300_Z5'),
    ('PP3300_EC_Z1','PP3300_Z1'),
    ('PP1800_FP_X','PP1800_S5'),
    ('PP3300_FP_X','PP3300_S5'),
    ('PP5000_TCHPAD_X','PPVAR_SYS'),
    ('PPVAR_VCCCORE_PH2','PPVAR_VCCCORE_IN'),
    ('PP3300_WWAN_X','PPVAR_SYS'),
    ('PP3300_GSC_Z1','PP3300_Z1'),
    ('PP3300_SSD_X','PP3300_S5'),
    ('PP3300_HDMI_X','PP3300_S5'),
    ('PP3300_WLAN_X','PP3300_S5'),
    ('PP1800_GSC_Z1','PP1800_Z1'),
    ('PP1500_RTC_Z5','PP3300_Z5'),
    ('PP5000_HDMI_X','PP5000_Z1'),
    ('PP3300_SD','PP3300_S5'),
    ('PPVAR_SYS_SD','PPVAR_SYS'),
    ('PPVAR_VBUS_IN','NA'),
    ('PP5000_FAN','PP5000_Z1'),
    ('PPVAR_SYS','NA'),
    ('PPVAR_VCCCORE_PH3','PPVAR_VCCCORE_IN'),
    ('PPVAR_VCCSA','PPVAR_VCCSA_IN'),
    ('PPVAR_VCCCORE_IN','PPVAR_SYS'),
    ('PPVAR_VCCGT_PH2','PPVAR_VCCGT_IN'),
    ('PP3300_TCHPAD_X','PP3300_S5'),
    ('PPVAR_VCCGT_PH1','PPVAR_VCCGT_IN'),
    ('PP1250_SOC_IN','PPVAR_SYS'),
]

GPIOS = [
]
