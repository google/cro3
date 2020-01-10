# -*- coding: utf-8 -*-
"""Define steps, package names, and directories for creating a Volteer variant

Copyright 2020 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
"""

from __future__ import print_function
import step_names

# List of steps (named in step_names.py) to run in sequence to create
# the new variant of the baseboard
step_list = [
    step_names.CB_VARIANT,
    # TODO(b/147483696)
    # step_names.CB_CONFIG,
    step_names.ADD_FIT,
    step_names.GEN_FIT,
    step_names.COMMIT_FIT,
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

# Package name for FSP
fsp = 'intel-tglfsp'

# Package name for the fitimage
fitimage_pkg = 'coreboot-private-files-baseboard-volteer'

# Directory for fitimage; append '~/trunk/src/'' in chroot, '~/chromiumos/src' outside
fitimage_dir = 'private-overlays/baseboard-volteer-private/sys-boot/'\
    'coreboot-private-files-baseboard-volteer'

# List of packages to cros_workon
workon_pkgs = ['coreboot', 'libpayload', 'vboot_reference', 'depthcharge', fsp,
    fitimage_pkg, 'chromeos-ec', 'chromeos-config-bsp-volteer-private']

# The emerge command
emerge_cmd = 'emerge-volteer'

# List of packages to emerge
emerge_pkgs = ['coreboot', 'libpayload', 'vboot_reference', 'depthcharge', fsp,
    fitimage_pkg, 'chromeos-ec', 'chromeos-config-bsp-volteer-private',
    'chromeos-config', 'chromeos-config-bsp', 'chromeos-config-bsp-volteer',
    'coreboot-private-files', fitimage_pkg, 'chromeos-bootimage']

# List of packages to emerge just to build the yaml
yaml_emerge_pkgs = ['chromeos-config-bsp', 'chromeos-config',
    'chromeos-config-bsp-volteer', 'chromeos-config-bsp-volteer-private']

# Directory for the private yaml file
private_yaml_dir = '~/trunk/src/private-overlays/overlay-volteer-private/'\
    'chromeos-base/chromeos-config-bsp-volteer-private'
