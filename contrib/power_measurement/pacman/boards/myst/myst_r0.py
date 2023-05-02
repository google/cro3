# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Config for myst r0"""

PACS = [
    # addr:ch  name                  nom   rsense
    ("0x10:0", "PPVAR_VDDCR_SR_VIN", 11.1, 0.05),
    ("0x10:1", "PPVAR_VDDCR_SOC_VIN", 11.1, 0.01),
    ("0x10:2", "PP1100_S0_N", 1.1, 0.005),
    ("0x10:3", "PPVAR_VDDCR_VIN", 11.1, 0.001),

    ("0x11:1", "PP1800_GSC_Z1", 1.8, 0.3),
    ("0x11:2", "PP3300_GSC_Z1", 3.3, 0.3),
    ("0x11:3", "PP0500_MEM_S0_VDD_MEMQ", 0.5, 0.001),

    ("0x12:0", "PP3300_Z1", 3.3, 0.005),
    ("0x12:1", "PPVAR_SYS_SUB", 11.1, 0.01),
    ("0x12:2", "PPVAR_MEM_S0", 0.78, 0.001),
    ("0x12:3", "PP0750_MISC_S5", 0.75, 0.01),

    ("0x13:0", "PP3300_S0", 3.3, 0.005),
    ("0x13:1", "PP1800_S0", 1.8, 0.01),
    ("0x13:2", "PP1800_S5", 1.8, 0.01),
    ("0x13:3", "PP3300_S5", 3.3, 0.1),

    ("0x14:0", "PP3300_WLAN_X", 3.3, 0.02),
    ("0x14:1", "PP0900_VDD2L_MEM_S3", 0.9, 1),
    ("0x14:2", "PP1050_VDD2H_MEM_S3", 1.05, 0.001),
    ("0x14:3", "PPVAR_VBUS_IN", 20.0, 0.001),

    ("0x15:0", "PP1800_VDD_18_S0", 1.8, 0.01),
    ("0x15:1", "PP1050_MEM_S3_VDDIO_MEM_S3", 1.05, 0.005),
    ("0x15:2", "PP1800_Z1", 1.8, 0.01),
    ("0x15:3", "PP1800_VDD_18_S5", 1.8, 0.01),

    ("0x16:0", "PPVAR_SYS_VIN_VDDQ_MEM_S0", 11.1, 0.1),
    ("0x16:1", "PP1800_VDD1_MEM_S3", 1.8, 0.3),
    ("0x16:2", "PP5000_S5", 5.0, 0.005),
    ("0x16:3", "PP0750_MISC_S0", 0.75, 0.005),

    ("0x17:0", "PP3300_VDD_33_S0", 3.3, 0.1),
    ("0x17:1", "PP3300_Z5_VDDBT_RTC", 3.3, 1000),
    ("0x17:2", "PP1800_VDDIO_AUDIO", 1.8, 0.2),
    ("0x17:3", "PP3300_VDD_33_S5", 3.3, 0.1),

    ("0x18:0", "PP1800_EC_Z1", 1.8, 1),
    ("0x18:2", "PP3300_Z5", 3.3, 0.5),
    ("0x18:3", "PP3300_EC_Z1", 3.3, 0.2),

    ("0x19:0", "PPVAR_BAT", 11.1, 0.005),
    ("0x19:1", "PPVAR_SYS", 11.1, 0.001),
    ("0x19:2", "PPVAR_SYS_KB_BL", 11.1, 0.3),

    ("0x1A:1", "PP3300_SD_S0", 3.3, 0.01),
    ("0x1A:3", "PP3300_SSD_S0", 3.3, 0.02),

    ("0x1B:0", "PP3300_CAM_X", 3.3, 0.02),
    ("0x1B:1", "PP3300_DISP_X", 3.3, 0.02),
    ("0x1B:2", "PP0900_RT_X", 0.9, 0.01),
    ("0x1B:3", "PPVAR_BL_PWR", 11.1, 0.2),

    ("0x1C:0", "PP5000_S5_SUB", 5.0, 0.005),
    ("0x1C:1", "PP3300_S5_SUB", 3.3, 0.5),
    ("0x1C:2", "PP3300_WWAN_X_SUB", 3.3, 0.01),
    ("0x1C:3", "PP0900_RT_X_SUB", 0.9, 0.01),
]

RAILS = [
    # rail             parent
    ("PPVAR_VDDCR_SR_VIN", "PPVAR_SYS"),
    ("PPVAR_VDDCR_SOC_VIN", "PPVAR_SYS"),
    ("PP1100_S0_N", "PPVAR_SYS"),
    ("PPVAR_VDDCR_VIN", "PPVAR_SYS"),

    ("PP1800_GSC_Z1", "PP1800_Z1"),
    ("PP3300_GSC_Z1", "PP3300_Z1"),
    ("PP0500_MEM_S0_VDD_MEMQ", "PP0500_VDDQ_MEM_S0"),

    ("PP3300_Z1", "PPVAR_SYS"),
    ("PPVAR_SYS_SUB", "PPVAR_SYS"),
    ("PPVAR_MEM_S0", "PPVAR_SYS"),
    ("PP0750_MISC_S5", "PPVAR_SYS"),

    ("PP3300_S0", "PP3300_Z1"),
    ("PP1800_S0", "PP1800_Z1"),
    ("PP1800_S5", "PP1800_Z1"),
    ("PP3300_S5", "PP3300_Z1"),

    ("PP3300_WLAN_X", "PP3300_Z1"),
    ("PP0900_VDD2L_MEM_S3", "PP3300_Z1"),
    ("PP1050_VDD2H_MEM_S3", "PPVAR_SYS"),
    ("PPVAR_VBUS_IN", "NA"),

    ("PP1800_VDD_18_S0", "PP1800_S0"),
    ("PP1050_MEM_S3_VDDIO_MEM_S3", "PP1050_VDD2H_MEM_S3"),
    ("PP1800_Z1", "PPVAR_SYS"),
    ("PP1800_VDD_18_S5", "PP1800_S5"),

    ("PPVAR_SYS_VIN_VDDQ_MEM_S0", "PPVAR_SYS"),
    ("PP1800_VDD1_MEM_S3", "PP1800_Z1"),
    ("PP5000_S5", "PPVAR_SYS"),
    ("PP0750_MISC_S0", "PPVAR_SYS"),

    ("PP3300_VDD_33_S0", "PP3300_S0"),
    ("PP3300_Z5_VDDBT_RTC", "PP3300_Z5"),
    ("PP1800_VDDIO_AUDIO", "PP1800_S5"),
    ("PP3300_VDD_33_S5", "PP3300_S5"),

    ("PP1800_EC_Z1", "PP1800_Z1"),
    ("PP3300_Z5", "PPVAR_SYS"),
    ("PP3300_EC_Z1", "PP3300_Z1"),

    ("PPVAR_BAT", "PPVAR_VBUS_IN"),
    ("PPVAR_SYS", "PPVAR_VBUS_IN"),
    ("PPVAR_SYS_KB_BL", "PPVAR_SYS"),

    ("PP3300_SD_S0", "PP3300_S0"),
    ("PP3300_SSD_S0", "PP3300_S0"),

    ("PP3300_CAM_X", "PP3300_Z1"),
    ("PP3300_DISP_X", "PP3300_Z1"),
    ("PP0900_RT_X", "PP5000_S5"),
    ("PPVAR_BL_PWR", "PPVAR_SYS"),

    ("PP5000_S5_SUB", "PPVAR_SYS_SUB"),
    ("PP3300_S5_SUB", "PP3300_Z1"),
    ("PP3300_WWAN_X_SUB", "PPVAR_SYS_SUB"),
    ("PP0900_RT_X_SUB", "PP5000_S5_SUB"),
]

GPIOS = [
    # addr  rail
    (0x10, "PG_PCORE_S0_OD"),
    (0x11, "SLP_S5_L"),
    (0x12, "PG_PP0750_MISC_S5"),
    (0x13, "SLP_S3_L"),
    (0x14, "EN_PWR_Z1"),
    (0x15, "PG_VDDQ_MEM_OD"),
    (0x16, "PG_GROUPC_S0_OD"),
    (0x17, "EN_PWR_S0"),
    (0x18, "EN_PWR_PCORE_S0"),
    (0x19, "PG_PP5000_S5"),
    (0x1A, "PG_LPDDR5_S3_OD"),
    (0x1B, "EN_PWR_S5"),
    (0x1C, "PG_PP3300_PP1200_S5_SUB"),
]
