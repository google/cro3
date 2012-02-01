#!/bin/sh

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

###############################################################################
#
# This script can be used to check the current battery or AC status.
# It also logs and disply the results for the given time interval.
# ( Ref: 22430 in chromium-os).
#
# Command syntax:
# ./power_info.sh time_in_seconds.
#
# Example:
#./power_info.sh 600 (10 minutes).
#
###############################################################################

# User definied flags.
TIME_IN_SECONDS=$1

# Usage function.
usage() {
  cat <<EOF
  $0 <time_in_seconds>
  example: ./power_info.sh 300
EOF
exit 0
}

# Condition to check number of command line arguments.
if [ $# != 1 ]; then
  usage
fi

# Condition to check the given argument is number or not.
if ! [ "$1" -eq "$1" 2> /dev/null ]
  then
    #echo "ERROR: Please provide number!" > /dev/stderr
    usage
fi

true=1

#Get current date and time.
DATETIME="`date '+%d%m%y_%H%M%S'`"

#File Name will be appended with current date and time.
#The format of the file name is "Power_Info_DDMMYY_HHMMSS.log".
FILENAME="Power_Info_${DATETIME}.log"

#log and display results for the given time.
while [ $true ]
do
   # Get online, state and percentage values from power-supply-info script,
   # then display and redirect to a file (Power_Info_DDMMYY_HHMMSS.log).
   /usr/bin/power-supply-info | egrep '(online|state|percentage)' 2>&1 | tee -a $FILENAME
   #log and display current time
   time=`date +%H:%M:%S`
   echo "  Time:             $time" 2>&1 | tee -a $FILENAME
   echo "                                                       " 2>&1 | tee -a $FILENAME
   #sleep till the given time elapses.
   sleep $TIME_IN_SECONDS
done

