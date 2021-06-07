# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FROM python:3.8-slim-buster AS build

RUN apt-get update \
    && apt-get install -y \
      ca-certificates \
      curl \
      lsb-release \
      iproute2 \
      iputils-ping \
      python2.7 \
      python-pip \
      rsync \
      ssh \
      sudo \
      wget

# grab gsutil
RUN echo \
    "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] \
    http://packages.cloud.google.com/apt cloud-sdk main" | \
    tee -a /etc/apt/sources.list.d/google-cloud-sdk.list && \
    curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | \
    apt-key --keyring /usr/share/keyrings/cloud.google.gpg  \
    add - && apt-get update -y && apt-get install google-cloud-sdk -y
RUN rm -rf /usr/lib/google-cloud-sdk/bin/anthoscli \
  /usr/lib/google-cloud-sdk/bin/kuberun

# Config the user
RUN useradd -m chromeos-test
# Add passwordless sudo for chromeos-test.
# TODO, Try to remove SUDO from containers
RUN echo 'chromeos-test ALL=NOPASSWD:ALL' > /etc/sudoers.d/chromeos-test

# Install all packages
COPY requirements.txt .
RUN pip2 install --upgrade pip
RUN pip2 install -r requirements.txt
RUN pip3 install -r requirements.txt

# TODO (dbeckett/shapiroc), this should be gen'd from the ebuild.
# deploy autotest_server packages
COPY autotest_server_package.tar.bz2 /tmp/autotest_server_package.tar.bz2
RUN tar -xvf /tmp/autotest_server_package.tar.bz2 -C /usr/local

# LXC gives chown/chgrp to root...
RUN chown -R chromeos-test:chromeos-test /usr/local/tast
RUN chown -R chromeos-test:chromeos-test /usr/local/autotest/

COPY shadow_config.ini /usr/local/autotest/
RUN chown -R chromeos-test:chromeos-test /usr/local/autotest/shadow_config.ini

# Test service *must* be cp'd into the dockerfile dir prior.
COPY testexecserver /usr/bin/

# Own testexecserver
RUN chown -R chromeos-test:chromeos-test /usr/bin/testexecserver

USER chromeos-test

# Configure the ssh for testing
RUN mkdir ~/.ssh
RUN  echo '\n\
Host * \n\
  StrictHostKeyChecking=no \n\
  IdentityFile %d/.ssh/testing_rsa \n\
  UserKnownHostsFile=/dev/null \n\
'> ~/.ssh/config

RUN cp /usr/local/autotest/utils/frozen_chromite/ssh_keys/testing_rsa ~/.ssh/
RUN chmod 400 ~/.ssh/testing_rsa

COPY shadow_config.ini .

# The upstream autotest code that run in the container uses this to determine
# it is running in a container.  Even though we are running docker not lxc
# the check is for the string lxc.
# See https://source.corp.google.com/chromeos_public/src/third_party/autotest/files/server/server_job.py;l=940
ENV container=lxc
