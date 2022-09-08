# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#!/bin/bash

###############################################################################
#                            Workflow for VM                                  #
###############################################################################
# Expects Chrome OS test image instance up and running in a VM, on port 9222. #
#                                                                             #
# This script:                                                                #
# 1) Deploys parser utils to the VM                                           #
# 2) Adds persistent audit rules to the VM (Replacing /etc/init/auditd.conf)  #
# 3) Reboots VM to collect bootup logs                                        #
# 4) Waits some time to increase the log volume                               #
# 5) Parses the collected logs in the VM and prints the syscall usage stats   #
###############################################################################


LOG_TAG="[INFO]"
AUDIT_SCRIPTS_DIR="/usr/local/network_traffic_auditor"
AUDITD_INIT_CONF_PATH="/etc/init/auditd.conf"

shopt -s expand_aliases

RSA_KEY=/usr/local/google/home/${USER}/chromiumos/src/scripts/mod_for_test_scripts/ssh_keys/testing_rsa
# TODO(zauri): add -q flag for quiet mode
alias scp_vm="scp -i $RSA_KEY -o StrictHostKeyChecking=no -o CheckHostIp=no -o UserKnownHostsFile=/dev/null -o User=root -o Port=9222"
alias ssh_vm="ssh -i $RSA_KEY -o StrictHostKeyChecking=no -o CheckHostIp=no -o UserKnownHostsFile=/dev/null -o User=root -o Port=9222 localhost"


# Renew credentials
echo "$LOG_TAG Renew gcert credentials:"
gcert


# Make the root mount wriateble
ssh_vm mount / -o remount,rw


# Push parser and monitorin script to VM
ssh_vm mkdir -p $AUDIT_SCRIPTS_DIR
echo "$LOG_TAG Pushing scripts to VM"
scp_vm ../parser.py run_monitoring.sh localhost:$AUDIT_SCRIPTS_DIR


# Swap auditd.conf file to allow syscall monitoring since boot up
# TODO(zauri): Add gerrit watch to react when auditd.conf file changes.
echo "$LOG_TAG Swapping etc/init/auditd.conf to append syscall monitoring rules"
scp_vm ../conf/auditd.conf localhost:$AUDITD_INIT_CONF_PATH

# Reboot
echo "$LOG_TAG Rebooting VM ..."
ssh_vm reboot


# Wait for reboot to finish
# TODO(zauri): Experienced premature exit, maybe need to change this logic.
TIMEOUT=5
while true
do
  sleep $TIMEOUT
  ssh_vm -q exit
  if [[ $? ]]; then
    break
  fi
  echo "$LOG_TAG waiting ..."
done
echo "$LOG_TAG Done, VM is running!"

# Run syscall monitoring
ssh_vm bash $AUDIT_SCRIPTS_DIR/run_monitoring.sh


####################
# Workflow for DUT #
####################
# TODO(zauri):
