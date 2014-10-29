# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module contains a list of artifact name related constants and methods."""

############ Artifact Names ############

# Note these are the available 'artifacts' that are known to the devserver. If
# you just need to stage a file from gs directly, use the files api. See the
# stage documentation for more info.

#### Update payload names. ####

# The name of artifact to stage a full update payload.
FULL_PAYLOAD = 'full_payload'

# The name of the artifact to stage all delta payloads for a build.
DELTA_PAYLOADS = 'delta_payloads'

# The payload containing stateful data not stored on the rootfs of the image.
STATEFUL_PAYLOAD = 'stateful'

#### The following are the names of images to stages. ####

# The base image i.e. the image without any test/developer enhancements.
BASE_IMAGE = 'base_image'

# The recovery image - the image used to recover a chromiumos device.
RECOVERY_IMAGE = 'recovery_image'

# The test image - the base image with both develolper and test enhancements.
TEST_IMAGE = 'test_image'

# The developer image - the base image with developer enhancements.
DEV_IMAGE = 'dev_image'

#### Autotest related packages. ####

# Autotest -- the main autotest directory without the test_suites subdir.
AUTOTEST = 'autotest'

# Control Files -- the autotest control files without the test_suites subdir.
CONTROL_FILES = 'control_files'

# Autotest Packages-- the autotest packages subdirectory.
AUTOTEST_PACKAGES = 'autotest_packages'

# Test Suites - just the test suites control files from the autotest directory.
TEST_SUITES = 'test_suites'

# AU Suite - The control files for the autotest autoupdate suite.
AU_SUITE = 'au_suite'

# AU Suite - The control files for the paygen autoupdate suite (depends
# on channel defined in devserver_constants).
PAYGEN_AU_SUITE_TEMPLATE = 'paygen_au_%(channel)s_suite'

#### Miscellaneous artifacts. ####

# Firmware tarball.
FIRMWARE = 'firmware'

# Tarball containing debug symbols for the given build.
SYMBOLS = 'symbols'

# The factory test image.
FACTORY_IMAGE = 'factory_image'

# In general, downloading one artifact usually indicates that the caller will
# want to download other artifacts later. The following map explicitly defines
# this relationship. Specifically:
# If X is requested, all items in Y should also get triggered for download.
REQUESTED_TO_OPTIONAL_MAP = {
  TEST_SUITES: [AUTOTEST],
}
