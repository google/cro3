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
DATABASE=us-central1:linux-patches-mysql-8

if [[ -e /etc/systemd/system/cloud-sql-proxy.service ]]; then
  sudo systemctl stop cloud-sql-proxy
fi

if [[ -e /etc/systemd/system/git-cookie-authdaemon.service ]]; then
  sudo systemctl stop git-cookie-authdaemon
fi

# Install Stackdriver logging agent
curl -sSO https://dl.google.com/cloudagents/install-logging-agent.sh
sudo bash install-logging-agent.sh
sudo rm install-logging-agent.sh

# Install or update needed software
sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get -y dist-upgrade
sudo DEBIAN_FRONTEND=noninteractive apt-get -yq install \
  git mysql-client default-libmysqlclient-dev build-essential \
  python3 python3-dev python3-venv python3-setuptools \
  libssl-dev libffi-dev nginx

# Fetch git-cookie-authdaemon to authenticate gerrit api requests
if [[ -e ${WORKSPACE}/gcompute-tools ]]; then
  git -C "${WORKSPACE}/gcompute-tools" pull
else
  git -C "${WORKSPACE}" clone https://gerrit.googlesource.com/gcompute-tools
fi

# Fetch source code
if [[ -e ${WORKSPACE}/dev-util ]]; then
  git -C "${WORKSPACE}/dev-util" pull
else
  git -C "${WORKSPACE}" clone https://chromium.googlesource.com/chromiumos/platform/dev-util
  ln -sf "${FINDMISSING}" "${WORKSPACE}/findmissing"
fi

# cloud_sql_proxy requires a secret file which can be retrieved via gcloud
# Note: this will generate a token that lasts forever (year 9999)
if [[ ! -e ${WORKSPACE}/secrets/linux_patches_robot_key.json ]]; then
  gcloud iam service-accounts keys \
    create "${WORKSPACE}/secrets/linux_patches_robot_key.json" \
    --iam-account=linux-patches-robot@chromeos-missing-patches.google.com.iam.gserviceaccount.com
fi

sudo wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 -O /usr/bin/cloud_sql_proxy
sudo chmod a+x /usr/bin/cloud_sql_proxy

# Setup git identity
git config --global user.name "Linux Patches Robot"
git config --global user.email "linux-patches-robot@chromeos-missing-patches.google.com.iam.gserviceaccount.com"

# Setup git hooks
mkdir -p "${WORKSPACE}/git-hooks"
curl -Lo "${WORKSPACE}/git-hooks/commit-msg" https://gerrit-review.googlesource.com/tools/hooks/commit-msg
chmod +x "${WORKSPACE}/git-hooks/commit-msg"

# Logs
sudo mkdir -p /var/log/findmissing/
sudo touch /var/log/findmissing/findmissing.log
sudo chown -R "${USER}:${USER}" /var/log/findmissing/

sudo sh -c "cat >/etc/logrotate.d/findmissing" <<EOF
/var/log/findmissing/findmissing.log {
    daily
    rotate 7
    missingok
    notifempty
    compress
    create 640 ${USER} ${USER}
}
EOF

# Python environment setup
rm -rf "${FINDMISSING}/env"
python3 -m venv "${FINDMISSING}/env"
# shellcheck disable=SC1091
source "${FINDMISSING}/env/bin/activate"
"${FINDMISSING}/env/bin/pip" install -r "${FINDMISSING}/requirements.txt"

# Put systemd configurations in correct location
sudo sh -c "cat >/etc/systemd/system/cloud-sql-proxy.service" <<EOF
[Unit]
Description=cloud-sql-proxy required to be running to access cloudsql database

Wants=network.target
After=syslog.target network-online.target

[Service]
User=${USER}
Type=simple
Environment="HOME=${HOME}"
ExecStart=/usr/bin/cloud_sql_proxy -instances=google.com:chromeos-missing-patches:${DATABASE}=tcp:3306 -credential_file=${WORKSPACE}/secrets/linux_patches_robot_key.json
Restart=on-failure
RestartSec=10
KillMode=process

[Install]
WantedBy=multi-user.target
EOF
sudo chmod 644 /etc/systemd/system/cloud-sql-proxy.service

sudo sh -c "cat >/etc/systemd/system/git-cookie-authdaemon.service" <<EOF
[Unit]
Description=git-cookie-authdaemon required to access git-on-borg from GCE

Wants=network.target
After=syslog.target network-online.target

[Service]
User=${USER}
Type=simple
Environment="HOME=${HOME}"
ExecStart=${WORKSPACE}/gcompute-tools/git-cookie-authdaemon --nofork
Restart=on-failure
RestartSec=10
KillMode=process

[Install]
WantedBy=multi-user.target
EOF
sudo chmod 644 /etc/systemd/system/git-cookie-authdaemon.service
sudo ln -sf /usr/bin/python3 /usr/bin/python

# Start service now
sudo systemctl daemon-reload
sudo systemctl start cloud-sql-proxy
sudo systemctl start git-cookie-authdaemon

# Start everytime on boot
sudo systemctl enable cloud-sql-proxy
sudo systemctl enable git-cookie-authdaemon
