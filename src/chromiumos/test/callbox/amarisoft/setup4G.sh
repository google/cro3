#!/bin/bash -e
#
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
#
# Sets up the amarisoft callbox with the 4G eNode-B configuration.

cp -r enb/* /root/enb/ || exit
cp -r mme/* /root/mme/ || exit

cd /root/enb/config/ || exit
# setup 4G radio
ln -sfn cros.enb.cfg enb.cfg

cd /root/mme/config/ || exit
ln -sfn cros-mme-ims.cfg mme.cfg
ln -sfn cros-ims.cfg ims.cfg

service lte restart
