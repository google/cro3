#!/bin/bash
# Copyright 2019 The Chromium OS Authors. All rights reserved.
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

# Add sources for apitrace.
echo "Adding sources and preferences for apitrace"
sudo tee -a /etc/apt/preferences.d/testing.pref << EOF
Package: *
Pin: release a=testing
Pin-Priority: 400
EOF

sudo tee -a /etc/apt/preferences.d/waffle.pref << EOF
Package: libwaffle-1-0
Pin: release a=testing
Pin-Priority: 505

Package: libwaffle-dev
Pin: release a=testing
Pin-Priority: 505
EOF

sudo tee -a /etc/apt/sources.list.d/testing.list << EOF
deb https://deb.debian.org/debian testing main
EOF

# Reload after configuring apt configuration.
echo "Updating APT"
sudo apt update

# Install packages.
echo "Installing glxinfo, glxgears, steam, and apitrace"
sudo apt install -y mesa-utils steam apitrace apitrace-tracers:i386
