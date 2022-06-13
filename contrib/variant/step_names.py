# -*- coding: utf-8 -*-
"""Define constants for the step names, so we don't misspell them later

Copyright 2020 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
"""

from __future__ import print_function

# pylint: disable=bad-whitespace
# Allow extra spaces around = so that we can line things up nicely
PROJECT_CONFIG  = 'project_config'
CB_VARIANT      = 'cb_variant'
CB_CONFIG       = 'cb_config'
DC_VARIANT      = 'dc_variant'
CRAS_CONFIG     = 'cras_config'
ADD_FIT         = 'add_fit'
GEN_FIT         = 'gen_fit'
COMMIT_FIT      = 'commit_fit'
EC_IMAGE        = 'ec_image'
ZEPHYR_EC       = 'zephyr_ec'
EC_BUILDALL     = 'ec_buildall'
ADD_PUB_YAML    = 'add_pub_yaml'
ADD_PRIV_YAML   = 'add_priv_yaml'
BUILD_CONFIG    = 'build_config'
FW_BUILD_CONFIG = 'fw_build_config'
EMERGE          = 'emerge'
PUSH            = 'push'
UPLOAD          = 'upload'
FIND            = 'find'
CALC_CQ_DEPEND  = 'calc_cq_depend'
ADD_CQ_DEPEND   = 'add_cq_depend'
RE_UPLOAD       = 're_upload'
CLEAN_UP        = 'clean_up'
ABORT           = 'abort'
# pylint: enable=bad-whitespace
