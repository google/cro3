#!/bin/sh

# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

DEVKIT_URL=$(grep ^CHROMEOS_DEVSERVER /etc/lsb-release | cut -d = -f 2-) 

if [ -z "$DEVKIT_URL" ]
then
  echo "No devkit server specified in /etc/lsb-release"
  exit 1
fi

sudo mount -o remount,rw /

sudo rm -f /etc/init/software-update.conf

sudo echo "deb http://chromeos-deb.corp.google.com/ubuntu" \
  "karmic main restricted multiverse universe" > /etc/apt/sources.list

sudo mkdir -p /var/cache/apt/archives/partial
sudo mkdir -p /var/log/apt
sudo apt-get update

wget "$DEVKIT_URL/static/devkit/devkit-custom.sh" -O - | sudo /bin/sh || true

sudo wget "$DEVKIT_URL/static/devkit/chromeos-builder" \
  -O /usr/bin/chromeos-builder
sudo chmod a+x /usr/bin/chromeos-builder

sudo wget "$DEVKIT_URL/static/devkit/devkit.conf" -O /etc/init/devkit.conf
