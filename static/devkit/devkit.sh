#!/bin/bash

# Copyright (c) 2009 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -e

DEVKIT_URL=$(grep ^CHROMEOS_DEVSERVER /etc/lsb-release | cut -d = -f 2-) 

if [ "x" = "x$DEVKIT_URL" ]
then
  echo "No devkit server specified in /etc/lsb-release"
  exit 1
fi

sudo mount -o remount,rw /

sudo rm -f /etc/init/software-update.conf

sudo echo "deb http://archive.ubuntu.com/ubuntu karmic main restricted multiverse universe" >> /tmp/devsrc 

sudo cp /tmp/devsrc /etc/apt/sources.list
sudo mkdir -p /var/cache/apt/archives/partial
sudo mkdir -p /var/log/apt
sudo apt-get update

sudo apt-get install -y vim || true
sudo apt-get install -y sshfs || true
sudo apt-get install -y gdb || true

sudo wget $DEVKIT_URL/static/devkit/vimrc.txt -O /home/chronos/.vimrc
sudo chmod a+r /home/chronos/.vimrc

sudo wget $DEVKIT_URL/static/devkit/chromeos-builder -O /usr/bin/chromeos-builder
sudo chmod a+x /usr/bin/chromeos-builder

sudo wget $DEVKIT_URL/static/devkit/devkit.conf -O /etc/init/devkit.conf
