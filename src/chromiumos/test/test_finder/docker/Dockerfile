# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FROM ubuntu:bionic
COPY cros-test-finder /usr/bin/


RUN mkdir -p /tmp/test
# Bring in metadata to 1 location
COPY *.pb /tmp/test/metadata/


# Own cros-test-finder & metadata
RUN chmod 755 /usr/bin/cros-test-finder
RUN chmod 644 /tmp/test/metadata/*.pb