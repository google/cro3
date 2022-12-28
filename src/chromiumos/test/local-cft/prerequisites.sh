#!/bin/bash

# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

sudo su - << SUDO
setup_docker () {
    # go/docker
    apt update
    glinux-add-repo docker-ce-"$(lsb_release -cs)"
    apt update
    apt install -y docker-ce

    systemctl stop docker
    ip link set docker0 down
    ip link del docker0

    cat << EOF | tee /etc/docker/daemon.json
    {
    "data-root": "/usr/local/google/docker",
    "bip": "192.168.9.1/24",
    "default-address-pools": [
        {
        "base": "192.168.11.0/22",
        "size": 24
        }
    ],
    "storage-driver": "overlay2",
    "debug": true,
    "registry-mirrors": ["https://mirror.gcr.io"]
    }
EOF

    systemctl start docker
    addgroup docker
    usermod -aG docker "${USER}"
}

setup_docker
apt update
apt install -y autossh google-cloud-sdk
SUDO

gcloud auth login
gcloud auth configure-docker

# newgrp starts a new shell, therefore must run last
newgrp docker
