# -*- coding: utf-8 -*-
"""Define constants for the step names, so we don't misspell them later

Copyright 2020 The Chromium OS Authors. All rights reserved.
Use of this source code is governed by a BSD-style license that can be
found in the LICENSE file.
"""

from __future__ import print_function

# pylint: disable=bad-whitespace
# Allow extra spaces around = so that we can line things up nicely
CB_VARIANT    = 'cb_variant'
CB_CONFIG     = 'cb_config'
CRAS_CONFIG   = 'cras_config'
ADD_FIT       = 'add_fit'
GEN_FIT       = 'gen_fit'
COMMIT_FIT    = 'commit_fit'
EC_IMAGE      = 'ec_image'
EC_BUILDALL   = 'ec_buildall'
ADD_YAML      = 'add_yaml'
BUILD_YAML    = 'build_yaml'
EMERGE        = 'emerge'
PUSH          = 'push'
UPLOAD        = 'upload'
FIND          = 'find'
CQ_DEPEND     = 'cq_depend'
CLEAN_UP      = 'clean_up'
# pylint: enable=bad-whitespace
