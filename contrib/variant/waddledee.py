# -*- coding: utf-8 -*-
"""Define steps, package names, and directories for creating a Dedede variant

Copyright 2020 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
"""

from __future__ import print_function
import step_names

# Name of the baseboard
base = 'dedede'

# List of steps (named in step_names.py) to run in sequence to create
# the new variant of the baseboard
step_list = [
    step_names.PROJECT_CONFIG,
    step_names.FW_BUILD_CONFIG,
    step_names.CB_VARIANT,
    step_names.CB_CONFIG,
    step_names.ADD_FIT,
    step_names.GEN_FIT,
    step_names.COMMIT_FIT,
    step_names.EC_IMAGE,
    step_names.EC_BUILDALL,
    step_names.EMERGE,
    step_names.PUSH,
    step_names.UPLOAD,
    step_names.FIND,
    step_names.CALC_CQ_DEPEND,
    step_names.ADD_CQ_DEPEND,
    step_names.RE_UPLOAD,
    step_names.CLEAN_UP]

# Base directory for coreboot
coreboot_dir = 'third_party/coreboot'

# Package name for FSP
fsp = 'intel-jslfsp'

# Package name for the fitimage
fitimage_pkg = 'coreboot-private-files-baseboard-dedede'

# Directory for fitimage; append '~/trunk/src/'' in chroot, '~/chromiumos/src' outside
fitimage_dir = 'private-overlays/baseboard-dedede-private/sys-boot/'\
    'coreboot-private-files-baseboard-dedede'

# Explanation of gen_fit_image command
fitimage_cmd = './gen_fit_image.sh %s <path_to_fit_kit> -b'

# List of packages to cros_workon
workon_pkgs = [
    'coreboot', 'libpayload', 'vboot_reference', 'depthcharge', fsp,
    fitimage_pkg, 'chromeos-ec', 'chromeos-config-bsp-dedede-private']

# The emerge command
emerge_cmd = 'emerge-dedede'

# List of packages to emerge
emerge_pkgs = [
    'coreboot', 'libpayload', 'vboot_reference', 'depthcharge', fsp,
    fitimage_pkg, 'chromeos-ec', 'chromeos-config-bsp-dedede-private',
    'chromeos-config', 'chromeos-config-bsp', 'coreboot-private-files',
    'chromeos-bootimage']

# List of packages to cros_workon to build the project config
config_workon_pkgs = ['chromeos-config-bsp-dedede-private']

# List of packages to emerge to build the project config
config_emerge_pkgs = ['chromeos-config-bsp-dedede-private']

# List of commits that will be uploaded with `repo upload`
repo_upload_list = [
    step_names.CB_CONFIG, step_names.COMMIT_FIT,
    step_names.EC_IMAGE, step_names.FW_BUILD_CONFIG]

# List of commits that will be pushed to review.coreboot.org
coreboot_push_list = [step_names.CB_VARIANT]

# List of steps that depend on other steps, and what those are.
# This list gets used for setting up Cq-Depend on the uploaded CLs.
depends = {
    step_names.CB_CONFIG: [step_names.FIND],
    step_names.FW_BUILD_CONFIG: [
        step_names.FIND, step_names.CB_CONFIG,
        step_names.COMMIT_FIT, step_names.EC_IMAGE]
}
