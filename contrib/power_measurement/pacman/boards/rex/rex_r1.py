# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Config for Rex Proto1"""

PACS = [
    # addr:ch   name                nom    rsense
    ("0x10:0", "PP0770_SOC_IN",    11.100, 0.010),  # R380
    ("0x10:1", "PPVAR_VCCSA_IN",   11.100, 0.010),  # R379
    ("0x10:2", "PP1250_SOC",        1.250, 0.010),  # R875
    ("0x10:3", "PP0770_SOC",        0.770, 0.010),  # R911

    ("0x11:0", "PP1065_MEM",        1.065, 0.003),  # R398
    ("0x11:1", "PP1800_MEM",        1.800, 0.010),  # RS2
    ("0x11:2", "PP1800_S5",         1.800, 0.003),  # R866
    ("0x11:3", "PP0500_MEM_S3",     0.500, 0.001),  # R874

    ("0x12:0", "PPVAR_VCCCORE_PH1", 1.650, 0.010),  # R906
    ("0x12:1", "PP3300_S5",         3.300, 0.005),  # R590
    ("0x12:2", "PP3300_Z5",         3.300, 0.010),  # R1085
    ("0x12:3", "PP5000_Z1",         5.000, 0.005),  # R591

    ("0x13:0", "PP3300_FCAM_X",     3.300, 0.010),  # R58
    ("0x13:1", "PP3300_HPS_X",      3.300, 0.010),  # R59
    ("0x13:2", "PP3300_EDP_X",      3.300, 0.020),  # R657
    ("0x13:3", "PP3300_TCHSCR_X",   3.300, 0.020),  # R658

    ("0x14:0", "PP1800_EC_Z1",      1.800, 0.010),  # R699
    ("0x14:1", "PPVAR_VCCGT_IN",    1.500, 0.010),  # R378
    ("0x14:2", "PP3300_Z1",         3.300, 0.100),  # R553
    ("0x14:3", "PP3300_EC_Z1",      3.300, 0.010),  # R700

    ("0x15:0", "PP1800_FP_X",       1.800, 0.500),  # R124
    ("0x15:1", "PP3300_FP_X",       3.300, 0.500),  # R123
    ("0x15:2", "PP5000_TCHPAD_X",   5.000, 0.010),  # R16
    ("0x15:3", "PPVAR_VCCCORE_PH2", 1.650, 0.010),  # R908

    ("0x16:0", "PP3300_WWAN_X",     3.300, 0.005),  # R235
    ("0x16:1", "PP3300_GSC_Z1",     3.300, 0.010),  # R415
    ("0x16:2", "PP3300_SSD_X",      3.300, 0.005),  # R236
    ("0x16:3", "PP3300_HDMI_X",     3.300, 0.020),  # R679

    ("0x17:0", "PP3300_WLAN_X",     3.300, 0.010),  # R873
    ("0x17:1", "PP1800_GSC_Z1",     1.800, 0.010),  # R414
    ("0x17:2", "PP1500_RTC_Z5",     1.500, 0.500),  # R832
    ("0x17:3", "PP5000_HDMI_X",     5.000, 0.010),  # R695

    ("0x18:0", "PP3300_SD",         3.300, 0.010),  # R143
    ("0x18:1", "PPVAR_SYS_SD",     11.100, 0.010),  # R144
    ("0x18:2", "PPVAR_VBUS_IN",    20.000, 0.001),  # R904
    ("0x18:3", "PP5000_FAN",        5.000, 0.010),  # R939

    ("0x19:0", "PPVAR_SYS",        11.100, 0.001),  # R905
    ("0x19:1", "PP1800_UWB_RF_X",   1.800, 0.100),  # R1052
    ("0x19:2", "PPVAR_VCCSA",       1.500, 0.010),  # R912
    ("0x19:3", "PPVAR_VCCCORE_IN", 11.100, 0.010),  # R399

    ("0x1A:0", "PP1800_UWB_DIG_X",  1.800, 0.100),  # R1051
    ("0x1A:1", "PP3300_TCHPAD_X",   3.300, 0.020),  # R15
    ("0x1A:2", "PPVAR_VCCGT",       1.500, 0.002),  # R909
    ("0x1A:3", "PP1250_SOC_IN",    11.100, 0.025),  # R448

    ("0x1B:0", "PP3300_USB_Z1",     3.300, 0.100),  # R655
    ("0x1B:1", "PP1065_SOC_S3",     1.065, 0.003),  # R876
    ("0x1B:2", "PP1800_Z1",         1.800, 0.100),  # R988
    ("0x1B:3", "PPVAR_SYS_EDP",    11.100, 0.005),  # R231

    ("0x1C:0", "PP1200_WCAM_X",     1.200, 0.010),  # R1151
    ("0x1C:1", "PP1800_WCAM_X",     1.800, 0.010),  # R1152
    ("0x1C:2", "PP3000_WCAM_VCM_X", 3.000, 0.010),  # R1153
    ("0x1C:3", "PP2800_WCAM_X",     2.800, 0.010),  # R1154
]

RAILS = [
    # rail                 parent
    ("PP0770_SOC_IN",     "PPVAR_SYS"),
    ("PPVAR_VCCSA_IN",    "PPVAR_SYS"),
    ("PP1250_SOC",        "PPVAR_SYS"),
    ("PP0770_SOC",        "PPVAR_SYS"),
    ("PP1065_MEM",        "PPVAR_SYS"),
    ("PP1800_MEM",        "PP5000_Z1"),
    ("PP1800_S5",         "PPVAR_SYS"),
    ("PP0500_MEM_S3",     "PP1065_MEM_S3"),
    ("PPVAR_VCCCORE_PH1", "PPVAR_VCCCORE_IN"),
    ("PP3300_S5",         "PPVAR_SYS"),
    ("PP3300_Z5",         "PPVAR_SYS"),
    ("PP5000_Z1",         "PPVAR_SYS"),
    ("PP3300_FCAM_X",     "PP3300_S5"),
    ("PP3300_HPS_X",      "PP3300_S5"),
    ("PP3300_EDP_X",      "PP3300_S5"),
    ("PP3300_TCHSCR_X",   "PP3300_S5"),
    ("PP1800_EC_Z1",      "PP1800_Z1"),
    ("PPVAR_VCCGT_IN",    "PPVAR_SYS"),
    ("PP3300_Z1",         "PP3300_Z5"),
    ("PP3300_EC_Z1",      "PP3300_Z1"),
    ("PP1800_FP_X",       "PP1800_S5"),
    ("PP3300_FP_X",       "PP3300_S5"),
    ("PP5000_TCHPAD_X",   "PPVAR_SYS"),
    ("PPVAR_VCCCORE_PH2", "PPVAR_VCCCORE_IN"),
    ("PP3300_WWAN_X",     "PPVAR_SYS"),
    ("PP3300_GSC_Z1",     "PP3300_Z1"),
    ("PP3300_SSD_X",      "PP3300_S5"),
    ("PP3300_HDMI_X",     "PP3300_S5"),
    ("PP3300_WLAN_X",     "PP3300_S5"),
    ("PP1800_GSC_Z1",     "PP1800_Z1"),
    ("PP1500_RTC_Z5",     "PP3300_Z5"),
    ("PP5000_HDMI_X",     "PP5000_Z1"),
    ("PP3300_SD",         "PP3300_S5"),
    ("PPVAR_SYS_SD",      "PPVAR_SYS"),
    ("PPVAR_VBUS_IN",     "NA"), #PPVAR_USB_C1_VBUS
    ("PP5000_FAN",        "PP5000_Z1"),
    ("PPVAR_SYS",         "PPVAR_VBUS_IN"),
    ("PP1800_UWB_RF_X",   "PP3300_S5"),
    ("PPVAR_VCCSA",       "PPVAR_VCCSA_IN"),
    ("PPVAR_VCCCORE_IN",  "PPVAR_SYS"),
    ("PP1800_UWB_DIG_X",  "PP1800_S5"),
    ("PP3300_TCHPAD_X",   "PP3300_S5"),
    ("PPVAR_VCCGT",       "PPVAR_VCCGT_IN"),
    ("PP1250_SOC_IN",     "PPVAR_SYS"),
    ("PP3300_USB_Z1",     "PP3300_Z5"),
    ("PP1065_SOC_S3",     "PPVAR_SYS"),
    ("PP1800_Z1",         "PP3300_Z1"),
    ("PPVAR_SYS_EDP",     "PPVAR_SYS"),
    ("PP1200_WCAM_X",     "PP1800_S5"),
    ("PP1800_WCAM_X",     "PP1800_S5"),
    ("PP3000_WCAM_VCM_X", "PP3300_S5"),
    ("PP2800_WCAM_X",     "PP3300_S5"),
]

GPIOS = []


