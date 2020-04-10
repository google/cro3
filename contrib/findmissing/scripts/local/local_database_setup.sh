#!/bin/bash
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# ./scripts/local/local_database_setup.sh

FINDMISSING_DIR="$(cd $(dirname $0)/../..; pwd)"
cd "${FINDMISSING_DIR}"

sudo apt-get update && sudo apt-get install google-cloud-sdk \
        python3-venv libmariadbclient-dev
sudo wget https://dl.google.com/cloudsql/cloud_sql_proxy.linux.amd64 \
        -O /usr/local/bin/cloud_sql_proxy
sudo chmod +x /usr/local/bin/cloud_sql_proxy

# Required for cloud_sql_proxy
# (https://cloud.google.com/sql/docs/mysql/sql-proxy#credentials-from-an-authenticated-cloud-sdk-client.)
gcloud auth login

# Creates env in findmissing top level directory
python3 -m venv env

# Activate so requirements can be installed in virtual env
source env/bin/activate

# pip install requirements line by line
pip install -q $(cat requirements.txt)
