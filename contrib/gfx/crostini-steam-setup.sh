#!/bin/bash
# Copyright 2019 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

set -ex

# Helper script to setup Steam testing environment.

# Steam requires i386 architecture.
echo "Adding i386 architecture"
sudo dpkg --add-architecture i386

# Add sources for Steam.
echo "Adding sources for Steam"
grep ^deb /etc/apt/sources.list | \
  head -1 | \
  sed -e 's/main/contrib non-free/' | \
  sudo tee -a /etc/apt/sources.list.d/steam.list

# Reload after configuring apt configuration.
echo "Updating APT"
sudo apt update

# TODO(davidriley): Remove this hack once a newer version of waffle has
# been published.
wget http://commondatastorage.googleapis.com/crosvm-apt-sandbox/waffle/libwaffle-1-0_1.6.0-4+b1_amd64.deb
wget http://commondatastorage.googleapis.com/crosvm-apt-sandbox/waffle/libwaffle-1-0_1.6.0-4+b1_i386.deb
sudo apt install -y ./libwaffle*.deb

# Install packages.
echo "Installing glxinfo, glxgears, steam, and apitrace"
sudo apt install -y zstd mesa-utils steam apitrace apitrace-tracers:i386
