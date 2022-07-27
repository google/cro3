#!/bin/bash
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# THIS IS A STARTUP SCRIPT THATS RUN IN A NEW GCE
# DO NOT RUN LOCALLY

# Before this script is run, make sure to have the following:
# 1) Create or attach persistent disk to the GCE instance to hold kernel_repositories

USER=chromeos_patches
HOME="/home/${USER}"
WORKSPACE="${HOME}/findmissing_workspace"
FINDMISSING="${WORKSPACE}/dev-util/contrib/findmissing"

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
git -C "${WORKSPACE}" clone https://gerrit.googlesource.com/gcompute-tools

# Fetch source code
git -C "${WORKSPACE}" clone https://chromium.googlesource.com/chromiumos/platform/dev-util
ln -sf "${FINDMISSING}" "${WORKSPACE}/findmissing"

# cloud_sql_proxy requires a secret file which can be retrieved via gcloud
# Note: this will generate a token that lasts forever (year 9999)
gcloud iam service-accounts keys \
  create "${WORKSPACE}/secrets/linux_patches_robot_key.json" \
  --iam-account=linux-patches-robot@chromeos-missing-patches.google.com.iam.gserviceaccount.com

sudo wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O /usr/bin/cloud_sql_proxy
sudo chmod a+x /usr/bin/cloud_sql_proxy

# Logs
sudo mkdir -p /var/log/findmissing/
sudo touch /var/log/findmissing/findmissing.log
sudo chown -R "${USER}:${USER}" /var/log/findmissing/


# Python environment setup
python3 -m venv "${FINDMISSING}/env"
source "${FINDMISSING}/env/bin/activate"
"${FINDMISSING}/env/bin/pip" install -r "${FINDMISSING}/requirements.txt"

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
