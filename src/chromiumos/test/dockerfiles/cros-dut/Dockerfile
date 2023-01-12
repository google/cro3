# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FROM ubuntu:bionic
COPY cros-dut /usr/bin/cros-dut

RUN mkdir -p ~/.ssh
COPY partner_testing_rsa ~/.ssh/
RUN chmod 400 /~/.ssh/partner_testing_rsa
