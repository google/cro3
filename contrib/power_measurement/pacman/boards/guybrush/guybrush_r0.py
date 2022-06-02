# Copyright 2022 The ChromiumOS Authors.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Config for guybrush r0"""

PACS = [
    # addr:ch  name           nom    rsense
    ('0x10:0', 'PPVAR_VDDCR', 0.000, 0.001),
    ('0x10:1', 'PPVAR_PCORE_SOC_IN', 0.000, 0.001),
    ('0x10:2', 'PPVAR_VDDCR_SOC_S0', 1.000, 0.001),
    ('0x10:3', 'PPVAR_VDDCR_S0_PH3', 1.000, 0.001),
    ('0x11:0', 'PPVAR_VDDCR_S0_PH2', 1.000, 0.001),
    ('0x11:1', 'PP3300_VDDBT_RTC', 3.300, 1000.000),
    ('0x11:2', 'PPVAR_VDDCR_S0_PH1', 1.000, 0.001),
    ('0x12:0', 'PP3300_S5_VDD_33_S5', 3.300, 0.200),
    ('0x12:1', 'PP3300_S0_VDD_33', 3.300, 0.200),
    ('0x12:2', 'PP1800_S5_VDD_18_S5', 1.800, 0.050),
    ('0x12:3', 'PP1800_S0_VDD_18', 1.800, 0.020),
    ('0x13:0', 'PP1800_S0_VDDIO_VPH', 1.800, 0.050),
    ('0x13:1', 'PP1800_S5_VDDIO_AUDIO', 1.800, 0.220),
    ('0x13:2', 'PP0750_VDDP_S5', 0.750, 0.020),
    ('0x13:3', 'PP0750_VDDP_S0', 0.750, 0.020),
    ('0x14:0', 'PP1100_SOC_MEM_S3', 1.100, 0.005),
    ('0x14:1', 'PP1100_MEM_S3', 1.100, 0.003),
    ('0x14:2', 'PP1800_MEM_S3', 1.800, 0.500),
    ('0x14:3', 'PP0600_MEM', 0.600, 0.030),
    ('0x15:0', 'PP3300_EC_Z1', 3.300, 0.220),
    ('0x15:1', 'PP1800_Z1', 1.800, 0.010),
    ('0x15:2', 'PP3300_Z1', 3.300, 0.005),
    ('0x15:3', 'PP3300_S0', 3.300, 0.010),
    ('0x16:0', 'PP3300_GSC_Z1', 3.300, 0.300),
    ('0x16:1', 'PP1800_GSC_Z1', 1.800, 1.000),
    ('0x16:2', 'PP5000_S5', 5.000, 0.005),
    ('0x16:3', 'PPVAR_SYS_KB_BL', 0.000, 0.050),
    ('0x17:0', 'PP3300_DISP_X', 3.300, 0.020),
    ('0x17:1', 'PPVAR_BL_PWR', 0.000, 0.100),
    ('0x17:2', 'PP3300_WWAN_X', 3.300, 0.015),
    ('0x17:3', 'PP3300_WLAN_X', 3.300, 0.030),
    ('0x18:0', 'PP1800_S0', 1.800, 0.010),
    ('0x18:1', 'PP1800_EC_Z1', 1.800, 1.000),
    ('0x18:2', 'PP3300_S5', 3.300, 0.100),
    ('0x18:3', 'PP1800_S5', 1.800, 0.030),
    ('0x19:0', 'PP3300_SD_S0', 3.300, 0.020),
    ('0x19:1', 'PP3300_SSD_S0', 3.300, 0.020),
    ('0x19:2', 'PP3300_Z5', 3.300, 0.500),
    ('0x19:3', 'PPVAR_SYS_DB', 0.000, 0.010),
    ('0x1A:0', 'PPVAR_SYS', 0.000, 0.001),
    ('0x1A:1', 'PPVAR_BAT_Q', 0.000, 0.005),
    ('0x1A:2', 'PPVAR_VBUS_IN', 0.000, 0.001),
    ('0x1B:0', 'PP5000_S5_DB', 5.000, 0.005),
    ('0x1B:1', 'PP3300_S5_DB', 3.300, 0.500),
    ('0x1B:2', 'PP1200_S5_DB', 1.200, 0.050),
]

RAILS = [
    # rail          parent
    ('PPVAR_VDDCR', 'PPVAR_SYS'),
    ('PPVAR_PCORE_SOC_IN', 'PPVAR_SYS'),
    ('PPVAR_VDDCR_SOC_S0', 'PPVAR_SYS'),
    ('PPVAR_VDDCR_S0_PH3', 'PPVAR_VDDCR'),
    ('PPVAR_VDDCR_S0_PH2', 'PPVAR_VDDCR'),
    ('PP3300_VDDBT_RTC', 'PP3300_Z5'),
    ('PPVAR_VDDCR_S0_PH1', 'PPVAR_VDDCR'),
    ('PP3300_S5_VDD_33_S5', 'PP3300_S5'),
    ('PP3300_S0_VDD_33', 'PP3300_S0'),
    ('PP1800_S5_VDD_18_S5', 'PP1800_S5'),
    ('PP1800_S0_VDD_18', 'PP1800_S0'),
    ('PP1800_S0_VDDIO_VPH', 'PP1800_S0'),
    ('PP1800_S5_VDDIO_AUDIO', 'PP1800_S5'),
    ('PP0750_VDDP_S5', 'PPVAR_SYS'),
    ('PP0750_VDDP_S0', 'PPVAR_SYS'),
    ('PP1100_SOC_MEM_S3', 'PP1100_MEM_S3'),
    ('PP1100_MEM_S3', 'PPVAR_SYS'),
    ('PP1800_MEM_S3', 'PP1800_Z1'),
    ('PP0600_MEM', 'PP3300_Z1'),
    ('PP3300_EC_Z1', 'PP3300_Z1'),
    ('PP1800_Z1', 'PPVAR_SYS'),
    ('PP3300_Z1', 'PPVAR_SYS'),
    ('PP3300_S0', 'PP3300_Z1'),
    ('PP3300_GSC_Z1', 'PP3300_Z1'),
    ('PP1800_GSC_Z1', 'PP1800_Z1'),
    ('PP5000_S5', 'PPVAR_SYS'),
    ('PPVAR_SYS_KB_BL', 'PPVAR_SYS'),
    ('PP3300_DISP_X', 'PP3300_Z1'),
    ('PPVAR_BL_PWR', 'PPVAR_SYS'),
    ('PP3300_WWAN_X', 'PPVAR_SYS'),
    ('PP3300_WLAN_X', 'PP3300_Z1'),
    ('PP1800_S0', 'PP1800_Z1'),
    ('PP1800_EC_Z1', 'PP1800_Z1'),
    ('PP3300_S5', 'PP3300_Z1'),
    ('PP1800_S5', 'PP1800_Z1'),
    ('PP3300_SD_S0', 'PP3300_S0'),
    ('PP3300_SSD_S0', 'PP3300_S0'),
    ('PP3300_Z5', 'PPVAR_SYS'),
    ('PPVAR_SYS_DB', 'PPVAR_SYS'),
    ('PPVAR_SYS', 'PPVAR_BAT_Q'),
    ('PPVAR_BAT_Q', 'NA'),
    ('PPVAR_VBUS_IN', 'NA'),
    ('PP5000_S5_DB', 'PPVAR_SYS_DB'),
    ('PP3300_S5_DB', 'PP3300_S5'),
    ('PP1200_S5_DB', 'PP5000_S5_DB'),
]

GPIOS = [
    # addr  rail
    (0x10, 'PG_PCORE_S0_OD'),
    (0x11, 'EN_PWR_PCORE_S0'),
    (0x12, 'SLP_S5_L'),
    (0x13, 'PG_PP5000_S5'),
    (0x14, 'EN_PP1100_MEM_S3'),
    (0x15, 'EN_PWR_Z1'),
    (0x16, 'EN_PWR_S5'),
    (0x17, 'PG_GROUPC_S0_OD'),
    (0x18, 'PG_PP0750_VDD_S5'),
    (0x19, 'EN_PWR_S0'),
    (0x1a, 'SLP_S3_L'),
    (0x1b, 'PG_PP1200_A_DB_OD'),
]
