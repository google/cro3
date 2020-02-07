# -*- coding: utf-8 -*-
"""Define steps, package names, and directories for creating a Trembyle variant

Copyright 2020 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
"""

from __future__ import print_function
import step_names

# Name of the baseboard
base = 'zork'

# List of steps (named in step_names.py) to run in sequence to create
# the new variant of the baseboard
step_list = [
    step_names.CB_VARIANT,
    step_names.CB_CONFIG,
    step_names.CRAS_CONFIG,
    step_names.EC_IMAGE,
    step_names.EC_BUILDALL,
    step_names.ADD_YAML,
    step_names.BUILD_YAML,
    step_names.EMERGE,
    step_names.PUSH,
    step_names.UPLOAD,
    step_names.FIND,
    step_names.CQ_DEPEND,
    step_names.CLEAN_UP]

# Base directory for coreboot
coreboot_dir = 'third_party/coreboot-zork'

# Base directory for coreboot configs (None=use default)
cb_config_dir = 'overlays/overlay-zork/sys-boot/coreboot-zork/files/configs'

# Package name for FSP
fsp = None

# Package name for the fitimage (None, because Zork doesn't use FIT)
fitimage_pkg = None

# Directory for fitimage (None, because Zork doesn't use FIT)
fitimage_dir = None

# Explanation of gen_fit_image command (None, because Zork doesn't use FIT)
fitimage_cmd = None

# List of packages to cros_workon
workon_pkgs = ['coreboot-zork', 'chromeos-ec',
    'chromeos-config-bsp-zork-private']

# The emerge command
emerge_cmd = 'emerge-zork'

# List of packages to emerge
emerge_pkgs = ['coreboot-zork', 'vboot_reference',
    'chromeos-ec', 'chromeos-config-bsp-zork-private',
    'chromeos-config', 'chromeos-config-bsp', 'chromeos-config-bsp-zork',
    'coreboot-private-files', 'chromeos-bootimage']

# List of packages to emerge just to build the yaml
yaml_emerge_pkgs = ['chromeos-config-bsp', 'chromeos-config',
    'chromeos-config-bsp-zork', 'chromeos-config-bsp-zork-private']

# Directory for the private yaml file
private_yaml_dir = '~/trunk/src/private-overlays/overlay-zork-private/'\
    'chromeos-base/chromeos-config-bsp-zork-private'
