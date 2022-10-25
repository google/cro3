#!/bin/bash
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# This script preloads custom settings and is run on the router after the
# flashing process. These settings configure the router to be run in a CROS lab
# environment.
#
# OpenWrt Image Builder docs: https://openwrt.org/docs/guide-user/additional-software/imagebuilder
# https://openwrt.org/docs/guide-developer/uci-defaults

# Configure SSH Settings to disallow password login, as only private key auth
# using the common CROS test key will be used.
uci set dropbear.@dropbear[0].RootPasswordAuth='off'
uci set dropbear.@dropbear[0].PasswordAuth='off'

# Add an interface to connect to lab network as a DHCP client.
uci set network.@device[0]=device
uci set network.@device[0].name='br-lan'
uci set network.@device[0].type='bridge'
uci set network.@device[0].ports='lan'
uci set network.lab=interface
uci set network.lab.proto='dhcp'
uci set network.lab.device='br-lan'

# Turn on wireless radios on by default.
uci set wireless.radio0.disabled='0'
uci set wireless.radio1.disabled='0'

# Remove unnecessary interfaces that will not be used in the lab. The tests will
# create their own interfaces.
uci del network.lan
uci del wireless.default_radio0
uci del wireless.default_radio1

# Commit and reload UCI changes.
uci commit dropbear
uci commit network
uci commit wireless
/etc/init.d/dropbear reload
/etc/init.d/network reload
/sbin/wifi reload

# Link hostapd_cli to the location our tests expect it to be.
ln -s /usr/sbin/hostapd_cli /usr/bin/hostapd_cli
