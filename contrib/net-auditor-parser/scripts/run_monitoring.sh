# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

#!/bin/bash

# TODO(zauri): split this code to several .sh files
# TODO(zauri): set up env variables
# TODO(zauri): what should be max_file_size in auditd.conf?
# TODO(zauri): what should be max_file_size_action in auditd.conf?
# TODO(zauri): add rules for 32-bit arch? Will need to include send() also.
# TODO(zauri): simulate managed user log-in


# This script:
# 1. Remounts the root directory as writeable
# 2. Creates a directory to store log snapshots
# 3. Initiates a network connection using curl
# 4. Checks OS updates using update_engine_client
# 5. Causes daemon crash (and restore) and sends crash logs
# 6. Dumps auditd logs
# 7. Runs parser over the stored logs and shows syscall utilization


# Constants
LOG_TAG="[INFO]"
AUDIT_LOGS_DIR="/usr/local/network_traffic_auditor/logs"
SLEEP_TIME=30 #TODO(zauri): Increase sleep time. Current value is for testing.


# Make root writable
mount / -o remount,rw


# Create directory to store logs
mkdir -p $AUDIT_LOGS_DIR


# Wait to capture more logs
echo "$LOG_TAG wait for $SLEEP_TIME seconds to collect more logs ..."
sleep $SLEEP_TIME


# Print uptime
echo $LOG_TAG Device is $(uptime -p)


# Surf the net
VISIT_URL="https://www.google.com"
echo "$LOG_TAG Visiting $VISIT_URL:"
curl $VISIT_URL > /dev/null


# Check for updates:
echo "$LOG_TAG Checking for OS updates:"
update_engine_client --check_for_update=true


# Send crash reports:
echo "$LOG_TAG Killing cros_healthd daemon:"
# Cause segfault to generate crash log
pkill -11 cros_healthd
# Provide consent to enable crash log uploading
touch /run/crash_reporter/mock-consent
# Upload crash
echo $LOG_TAG Sending crash reports:
crash_sender --dev --ignore_hold_off_time --max_spread_time=0 # TODO(zauri): not showing sending reports like gpaste/5508041068773376


# Dump logs since the most recent boot time.
# Format of the file is $AUDIT_LOGS_DIR/YYMMDD_HHMMSS.log representing
# the time when the logs were collected.
boot_time=$(uptime -s)
boot_time="${boot_time:5:2}/${boot_time:8:2}/${boot_time:2:2} ${boot_time:11}"
echo $LOG_TAG boot time is: $boot_time
echo $LOG_TAG current time is: $(date +'%m/%d/%y %H:%M:%S')

# TODO(zauri): How to publish this variable?
log_file=$(date +%y%m%d_%H%M%S)
log_file=${AUDIT_LOGS_DIR}/${log_file}.log

echo $LOG_TAG Storing logs in ${log_file} ...
ausearch -i --start ${boot_time} --input-logs > ${log_file}
echo "$LOG_TAG Done."


# Run parser
# NOTE: Expecting the parser script in the same dir
# TODO(zauri): Use os.path to run the parser
PARSER=parser.py
echo $LOG_TAG Parsing log files ...
python3 $PARSER $log_file
