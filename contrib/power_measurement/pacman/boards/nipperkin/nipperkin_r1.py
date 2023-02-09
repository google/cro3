# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Config for nipperkin dvt"""

PACS = [
    # addr:ch  name           nom    rsense
    ("0x10:0", "PPVAR_VDDCR", 0.600, 0.003),
    ("0x10:1", "PPVAR_VDDCR_SOC", 0.600, 0.010),
    ("0x10:2", "PP1800_S0", 1.800, 0.010),
    ("0x10:3", "PP1800_S5", 1.800, 0.030),
    ("0x11:0", "PP3300_S5_VDD_33_S5", 3.300, 0.010),
    ("0x11:1", "PP3300_S0_VDD_33", 3.300, 0.010),
    ("0x11:2", "PP1800_S5_VDD_18_S5", 1.800, 0.005),
    ("0x11:3", "PP1800_S0_VDD_18", 1.800, 0.010),
    ("0x12:0", "PP1100_MEM_S3_VDDIO_MEM_S3", 1.100, 0.003),
    ("0x12:1", "PP1100_MEM_S3", 1.100, 0.003),
    ("0x12:2", "PP1800_MEM_S3", 1.800, 0.500),
    ("0x12:3", "PP0600_MEM", 0.600, 0.010),
    ("0x13:1", "PP1800_S5_VDDIO_AUDIO", 1.800, 0.005),
    ("0x13:2", "PP0750_VDDP_S5", 0.750, 0.020),
    ("0x13:3", "PP0750_VDDP_S0", 0.750, 0.020),
    ("0x14:0", "PP3300_S5", 3.300, 0.100),
    ("0x14:1", "PP1800_Z1", 1.800, 0.010),
    ("0x14:2", "PP3300_Z1", 3.300, 0.005),
    ("0x14:3", "PP3300_S0", 3.300, 0.010),
    ("0x15:0", "PP3300_GSC_Z1", 3.300, 0.300),
    ("0x15:1", "PP3300_SSD_S0", 3.300, 0.020),
    ("0x15:2", "PP5000_S5", 5.000, 0.005),
    ("0x15:3", "PP3300_SD_S0", 3.300, 0.020),
    ("0x16:0", "PP3300_DISP_X", 3.300, 0.020),
    ("0x16:1", "PPVAR_BL_PWR", 11.000, 0.100),
    ("0x16:3", "PP3300_WLAN_X", 3.300, 0.005),
    ("0x17:0", "PPVAR_SYS", 11.000, 0.001),
    ("0x17:1", "PPVAR_BAT", 11.000, 0.005),
    ("0x17:2", "PPVAR_VBUS_IN", 15.000, 0.001),
    ("0x17:3", "PPVAR_SYS_DB", 11.000, 0.010),
]

RAILS = [
    # rail          parent
    ("PPVAR_VDDCR", "PPVAR_SYS"),
    ("PPVAR_VDDCR_SOC", "PPVAR_SYS"),
    ("PP1800_S0", "PP1800_Z1"),
    ("PP1800_S5", "PP1800_Z1"),
    ("PP3300_S5_VDD_33_S5", "PP3300_S5"),
    ("PP3300_S0_VDD_33", "PP3300_S0"),
    ("PP1800_S5_VDD_18_S5", "PP1800_S5"),
    ("PP1800_S0_VDD_18", "PP1800_S0"),
    ("PP1100_MEM_S3_VDDIO_MEM_S3", "PP1100_MEM_S3"),
    ("PP1100_MEM_S3", "PPVAR_SYS"),
    ("PP1800_MEM_S3", "PP1800_Z1"),
    ("PP0600_MEM", "PP3300_Z1"),
    ("PP1800_S5_VDDIO_AUDIO", "PP1800_S5"),
    ("PP0750_VDDP_S5", "PPVAR_SYS"),
    ("PP0750_VDDP_S0", "PPVAR_SYS"),
    ("PP3300_S5", "PP3300_Z1"),
    ("PP1800_Z1", "PPVAR_SYS"),
    ("PP3300_Z1", "PPVAR_SYS"),
    ("PP3300_S0", "PP3300_Z1"),
    ("PP3300_GSC_Z1", "PP3300_Z1"),
    ("PP3300_SSD_S0", "PP3300_S0"),
    ("PP5000_S5", "PPVAR_SYS"),
    ("PP3300_SD_S0", "PP3300_S0"),
    ("PP3300_DISP_X", "PP3300_Z1"),
    ("PPVAR_BL_PWR", "PPVAR_SYS"),
    ("PP3300_WWAN_X", "PPVAR_SYS_DB"),
    ("PP3300_WLAN_X", "PP3300_Z1"),
    ("PPVAR_SYS", "PPVAR_BAT"),
    ("PPVAR_BAT", "NA"),
    ("PPVAR_VBUS_IN", "NA"),
    ("PPVAR_SYS_DB", "PPVAR_SYS"),
]

GPIOS = [
    # addr  rail
    (0x10, "PG_PCORE_S0_OD"),
    (0x11, "SLP_S5_L"),
    (0x12, "EN_PP1100_MEM_S3"),
    (0x13, "SLP_S3_L"),
    (0x14, "EN_PWR_Z1"),
    (0x15, "PG_PP0750_VDDP_S5"),
    (0x16, "PG_GROUPC_S0_OD"),
    (0x17, "EN_PWR_S0"),
]
