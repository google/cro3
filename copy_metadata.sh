#! /bin/bash -e

# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This script copy the test metadata from build to local test directory
# Example:
# ./copy_metadata.sh hana ./src/chromiumos/test/execution/data/metadata
# This script is temporary solution for testing of testexecserver.
# It will be removed after we implement a permanent method to export
# test metadata to a single directory.

board=$1
dest=$2

if [ -z "${board}" ]
then
    echo "board needs to be specified"
    exit 1
fi
if [ -z "${dest}" ]
then
    echo "desination needs to be specified"
    exit 1
fi

rm -rf "${dest:?}"/*
mkdir -p "${dest:?}"/tast/local "${dest:?}"/tast/remote "${dest:?}"/autotest

cp -p /build/"${board}"/usr/local/build/autotest/autotest_metadata.pb "${dest}"/autotest
cp -p /build/"${board}"/usr/share/tast/metadata/local/cros.pb "${dest}"/tast/local
cp -p /build/"${board}"/build/share/tast/metadata/local/crosint.pb "${dest}"/tast/local
cp -p /usr/share/tast/metadata/remote/cros.pb "${dest}"/tast/remote
