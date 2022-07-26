#!/bin/bash
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# THIS IS A STARTUP SCRIPT THATS RUN IN A NEW GCE
# DO NOT RUN LOCALLY

# Before this script is run, make sure to have the following:
# 1) Create or attach persistent disk to the GCE instance to hold kernel_repositories

# Install Stackdriver logging agent
curl -sSO https://dl.google.com/cloudagents/install-logging-agent.sh
sudo bash install-logging-agent.sh
sudo rm install-logging-agent.sh

# Install or update needed software
sudo apt-get update
sudo apt-get dist-upgrade
sudo apt-get install -yq \
  git mysql-client default-libmysqlclient-dev build-essential \
  python3 python3-dev python3-venv python3-setuptools \
  libssl-dev libffi-dev nginx

# Fetch git-cookie-authdaemon to authenticate gerrit api requests
sudo git -C /opt/ clone https://gerrit.googlesource.com/gcompute-tools

# Fetch source code
sudo git -C /opt/ clone https://chromium.googlesource.com/chromiumos/platform/dev-util

# Copies cloned repository to chromeos_patches home directory
sudo /opt/dev-util/contrib/findmissing/scripts/gce/sync_remote_to_gce.sh

# cloud_sql_proxy requires a secret file which can be retrieved via gcloud
# Note: this will generate a token that lasts forever (year 9999)
sudo gcloud iam service-accounts keys \
  create /home/chromeos_patches/secrets/linux_patches_robot_key.json \
  --iam-account=linux-patches-robot@chromeos-missing-patches.google.com.iam.gserviceaccount.com

sudo wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O /usr/bin/cloud_sql_proxy
sudo chmod a+x /usr/bin/cloud_sql_proxy

sudo mkdir -p /home/chromeos_patches/kernel_repositories/
sudo mount -o discard,defaults /dev/sdb /home/chromeos_patches/kernel_repositories/
sudo chmod a+w /home/chromeos_patches/kernel_repositories/

# Logs for chromeos_patches
sudo mkdir -p /var/log/findmissing/
sudo touch /var/log/findmissing/findmissing.log

# Set ownership to newly created account
sudo chown -R chromeos_patches:chromeos_patches /var/log/findmissing/
sudo chown -R chromeos_patches:chromeos_patches /opt/dev-util/
sudo chown -R chromeos_patches:chromeos_patches /home/chromeos_patches/

# Python environment setup
python3 -m venv /home/chromeos_patches/env
source /home/chromeos_patches/env/bin/activate
/home/chromeos_patches/env/bin/pip install -r /home/chromeos_patches/requirements.txt

# Put systemd configurations in correct location
sudo cp /home/chromeos_patches/config/systemd/cloud-sql-proxy.service /etc/systemd/system/
sudo cp /home/chromeos_patches/config/systemd/git-cookie-authdaemon.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/cloud-sql-proxy.service
sudo chmod 644 /etc/systemd/system/git-cookie-authdaemon.service

sudo cp /home/chromeos_patches/config/logrotate/findmissing /etc/logrotate.d/

# Start service now
sudo systemctl start cloud-sql-proxy
sudo systemctl start git-cookie-authdaemon

# Start everytime on boot
sudo systemctl enable cloud-sql-proxy
sudo systemctl enable git-cookie-authdaemon
