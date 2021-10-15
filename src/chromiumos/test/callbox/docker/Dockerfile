# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FROM ubuntu:bionic
COPY cellular .
RUN apt update && apt-get -y install python3 && \
    apt-get -y install python3-pip
RUN pip3 install --no-cache-dir --upgrade pip && \
    pip3 install --no-cache-dir -r requirements.txt
