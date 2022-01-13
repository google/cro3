# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# These devices are pac19next (4-channels/i2c address) devices
INAS = [
    #    drvname,   slv,       name,            nom,   sense,mux,  is_calib
    ('pac19next','0x10:0','PPVAR_VDDCR',0.600,0.003,'rem',True),
    ('pac19next','0x10:1','PPVAR_VDDCR_SOC',0.600,0.01,'rem',True),
    ('pac19next','0x10:2','PP1800_S0',1.800,0.01,'rem',True),
    ('pac19next','0x10:3','PP1800_S5',1.800,0.03,'rem',True),

    ('pac19next','0x11:0','PP3300_S5_VDD_33_S5',3.300,0.01,'rem',True),
    ('pac19next','0x11:1','PP3300_S0_VDD_33',3.300,0.01,'rem',True),
    ('pac19next','0x11:2','PP1800_S5_VDD_18_S5',1.800,0.005,'rem',True),
    ('pac19next','0x11:3','PP1800_S0_VDD_18',1.800,0.01,'rem',True),

    ('pac19next','0x12:0','PP1100_MEM_S3_VDDIO_MEM_S3',1.100,0.0025,'rem',True),
    ('pac19next','0x12:1','PP1100_MEM_S3',1.100,0.003,'rem',True),
    ('pac19next','0x12:2','PP1800_MEM_S3',1.800,0.5,'rem',True),
    ('pac19next','0x12:3','PP0600_MEM',0.600,0.01,'rem',True),

    ('pac19next','0x13:1','PP1800_S5_VDDIO_AUDIO',1.800,0.005,'rem',True),
    ('pac19next','0x13:2','PP0750_VDDP_S5',0.750,0.02,'rem',True),
    ('pac19next','0x13:3','PP0750_VDDP_S0',0.750,0.02,'rem',True),

    ('pac19next','0x14:0','PP3300_S5',3.300,0.1,'rem',True),
    ('pac19next','0x14:1','PP1800_Z1',1.800,0.01,'rem',True),
    ('pac19next','0x14:2','PP3300_Z1',3.300,0.005,'rem',True),
    ('pac19next','0x14:3','PP3300_S0',3.300,0.01,'rem',True),

    ('pac19next','0x15:0','PP3300_GSC_Z1',3.300,0.3,'rem',True),
    ('pac19next','0x15:1','PP3300_SSD_S0',3.300,0.02,'rem',True),
    ('pac19next','0x15:2','PP5000_S5',5.000,0.005,'rem',True),
    ('pac19next','0x15:3','PP3300_SD_S0',3.300,0.02,'rem',True),

    ('pac19next','0x16:0','PP3300_DISP_X',3.300,0.02,'rem',True),
    ('pac19next','0x16:1','PPVAR_BL_PWR',11.000,0.1,'rem',True),
#    ('pac19next','0x16:2','PP3300_WWAN_X',3.300,0.015,'rem',True),
    ('pac19next','0x16:3','PP3300_WLAN_X',3.300,0.005,'rem',True),

    ('pac19next','0x17:0','PPVAR_SYS',11.000,0.001,'rem',True),
    ('pac19next','0x17:1','PPVAR_BAT',11.000,0.005,'rem',True),
    ('pac19next','0x17:2','PPVAR_VBUS_IN',15.000,0.001,'rem',True),
    ('pac19next','0x17:3','PPVAR_SYS_DB',11.000,0.01,'rem',True),
]
