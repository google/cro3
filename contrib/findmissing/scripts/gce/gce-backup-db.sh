#!/bin/bash
#
# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


USER=chromeos_patches
HOME="/home/${USER}"
WORKSPACE="${HOME}/findmissing_workspace"
DATABASE=us-central1:linux-patches-mysql-8
PORT=${1:-8000}

cloud_sql_proxy \
    -instances="google.com:chromeos-missing-patches:${DATABASE}=tcp:${PORT}" \
    -credential_file="${WORKSPACE}/secrets/linux_patches_robot_key.json" &
pid=$!
echo "Started cloud_sql_proxy at port ${PORT}, pid ${pid}"

while ! ss -tln | awk '{print $4}' | grep -q ":${PORT}$";
do
    echo -n "."
    sleep 0.5
done

mysqldump \
    -u linux_patches_robot \
    -h 127.0.0.1 -P "${PORT}" \
    --set-gtid-purged=OFF linuxdb >/tmp/dump.sql
echo "Dumped to /tmp/dump.sql"

kill -TERM "${pid}"
wait
echo "Killed cloud_sql_proxy pid ${pid}"

echo "Run the following command for restoring DB:"
echo "  mysql -u linux_patches_robot -h 127.0.0.1 linuxdb </tmp/dump.sql"
