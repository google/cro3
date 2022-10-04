#!/bin/bash
#
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# ./scripts/local/local_database_setup.sh

FINDMISSING="$(cd "$(dirname "$0")/../.." || exit; pwd)"

WORKSPACE="${HOME}/findmissing_workspace"
mkdir -p "${WORKSPACE}"
cd "${WORKSPACE}" || exit

PROJECT="google.com:chromeos-missing-patches"

sudo apt-get update

packages=()
packages+=(google-cloud-sdk)
packages+=(python3-venv)
packages+=(libmariadb-dev)
packages+=(python3-dev)
for p in "${packages[@]}"; do
    sudo apt-get install "${p}"
done

sudo wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 \
        -O /usr/local/bin/cloud_sql_proxy
sudo chmod +x /usr/local/bin/cloud_sql_proxy

if [[ $(gcloud config get project) != "${PROJECT}" ]]; then
    # Required for cloud_sql_proxy
    # (https://cloud.google.com/sql/docs/mysql/sql-proxy#credentials-from-an-authenticated-cloud-sdk-client.)
    gcloud auth login --no-launch-browser

    gcloud config set project "${PROJECT}"
fi

# Creates env in findmissing top level directory
python3 -m venv env

# pip install requirements line by line
# shellcheck disable=SC2046
./env/bin/pip install -q $(cat "${FINDMISSING}/requirements.txt")
