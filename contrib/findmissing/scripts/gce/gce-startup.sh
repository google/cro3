#!/bin/bash
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# THIS IS A STARTUP SCRIPT THATS RUN IN A NEW GCE
# DO NOT RUN LOCALLY

# Install Stackdriver logging agent
curl -sSO https://dl.google.com/cloudagents/install-logging-agent.sh
sudo bash install-logging-agent.sh

# Install or update needed software
apt-get update
apt-get install -yq git supervisor python3 python3-pip python3-venv
pip install --upgrade pip virtualenv

# Account to own server process
useradd -m -d /home/chromeos_patches chromeos_patches

# Fetch source code
git clone https://chromium.googlesource.com/chromiumos/platform/dev-util /opt/

# Copies cloned repository to chromeos_patches home directory
/opt/dev-util/contrib/findmissing/scripts/sync_remote_to_gce.sh

# Python environment setup
python3 -m venv /home/chromeos_patches/env
source /home/chromeos_patches/env/bin/activate
/home/chromeos_patches/env/bin/pip install -r \
  /home/chromeos_patches/env/bin/requirements.txt

# Set ownership to newly created account
chown -R chromeos_patches:chromeos_patches /opt/dev-util/
chown -R chromeos_patches:chromeos_patches /home/chromeos_patches/

# Put supervisor configuration in proper place
cp /home/chromeos_patches/config/chromeos-patches-app.conf \
  /etc/supervisor/conf.d/chromeos-patches-app.conf

# Start service via supervisorctl
supervisorctl reread
supervisorctl update
