# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

FROM python:3.8-slim-buster AS build

RUN apt-get update \
    && apt-get install -y \
      ca-certificates \
      curl \
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

# Point /usr/bin/python3 to usr/local/bin/python3. See b/191884161
RUN sudo rm /usr/bin/python3*
RUN sudo ln -s /usr/local/bin/python3 /usr/bin/python3

# Config the user
RUN useradd -m chromeos-test
# Add passwordless sudo for chromeos-test.
# TODO, Try to remove SUDO from containers
RUN echo 'chromeos-test ALL=NOPASSWD:ALL' > /etc/sudoers.d/chromeos-test

# Install all packages
COPY requirements_py2.txt .
COPY requirements_py3.txt .

RUN pip2 install --upgrade pip
RUN pip2 install -r requirements_py2.txt
RUN pip3 install -r requirements_py3.txt

# deploy autotest & tast packages
COPY --chown=chromeos-test:chromeos-test autotest/ /usr/local/autotest
COPY --chown=chromeos-test:chromeos-test tast/tast /usr/bin/tast
COPY --chown=chromeos-test:chromeos-test tast/remote_test_runner /usr/bin/remote_test_runner
COPY --chown=chromeos-test:chromeos-test tast/bundles/ /usr/libexec/tast/bundles
COPY --chown=chromeos-test:chromeos-test tast/data/ /usr/share/tast/data
COPY --chown=chromeos-test:chromeos-test tast/vars/ /etc/tast/vars

COPY shadow_config.ini /usr/local/autotest/
RUN chown -R chromeos-test:chromeos-test /usr/local/autotest/shadow_config.ini

RUN touch /usr/local/f20container

# Test service *must* be cp'd into the dockerfile dir prior.
COPY cros-test /usr/bin/

RUN mkdir -p /tmp/test
# Bring in metadata to 1 location
COPY *.pb /tmp/test/metadata/

RUN sudo ln -s /usr/local/autotest/site_utils/test_that.py /usr/bin/test_that

# Own cros-test & metadata
RUN chown -R chromeos-test:chromeos-test /usr/bin/cros-test
RUN chmod 755 /usr/bin/cros-test
RUN chown -R chromeos-test:chromeos-test /tmp/test/
RUN chmod 755 /tmp/test/metadata/*.pb

USER chromeos-test

# Configure the ssh for testing
RUN mkdir ~/.ssh
RUN  echo '\n\
Host android* brillo* chromeos1* chromeos2* chromeos3* chromeos4* chromeos5* chromeos6* chromeos7* chromeos9* autotest*.vrlab* jetstream* satlab* cros-* \n\
  GSSAPIKeyExchange no \n\
  GSSAPITrustDns no \n\
  GSSAPIDelegateCredentials no \n\
  GSSAPIAuthentication no \n\
  GSSAPIKeyExchange no \n\
  GSSAPIClientIdentity no \n\
  GSSAPIRenewalForcesRekey no \n\
  ForwardAgent no \n\
  ForwardX11 no \n\
  PreferredAuthentications publickey \n\
  StrictHostKeyChecking no \n\
  User root \n\
  IdentityFile %d/.ssh/testing_rsa \n\
\n\
Host * \n\
  StrictHostKeyChecking=no \n\
  IdentityFile %d/.ssh/testing_rsa \n\
  IdentityFile %d/.ssh/autotest_internal_rsa \n\
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
