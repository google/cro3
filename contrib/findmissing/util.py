#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Helper functions used by various commands

preliminary_check_decorator():
    Check if environment is set up correctly.

cloud_sql_proxy_decorator():
    Start and stop cloud_sql_proxy.
"""


import logging
import os
import subprocess
import time

import common


def check_service_key_secret_exists():
    """Raises an error if the service account secret key file does not exist.

    This can be generated on GCP under service accounts (Generate service token)
    This file should automatically be generated when running the gce-startup.sh script.
    """
    secret_file_path = os.path.join(common.HOMEDIR, 'secrets/linux_patches_robot_key.json')

    if not os.path.exists(secret_file_path):
        raise FileNotFoundError('Service token secret file %s not found' % secret_file_path)


def check_service_running(keyword):
    """Raises an error if there is no running process commands that match `keyword`."""
    process_grep = ['pgrep', '-f', keyword]
    try:
        subprocess.run(process_grep, check=True, stdout=subprocess.DEVNULL,
                        encoding='utf-8', errors='ignore')
    except subprocess.CalledProcessError as e:
        raise ProcessLookupError('Service %s is not running.' % keyword) from e


def check_cloud_sql_proxy_running():
    """Raises an error if cloud_sql_proxy service is not running."""
    check_service_running('cloud_sql_proxy')


def check_git_cookie_authdaemon_running():
    """Raises an error if git-cookie-authdaemon service is not running."""
    check_service_running('git-cookie-authdaemon')


def preliminary_check_decorator(is_gce):
    """Decorator for performing environment related checks."""
    def wrap_preliminary_check(f):
        """Inner function that wraps method with preliminary check."""
        def wrapped_preliminary_check(*args):
            """Sanity checks on state of environment before executing decorated function."""
            if is_gce:
                # Ensures we have service account credentials to connect to cloudsql (GCP)
                check_service_key_secret_exists()

            # Ensure cloudsql proxy is running to allow connection
            check_cloud_sql_proxy_running()

            if is_gce:
                level = logging.INFO
                # Ensure we have token to allow service account to perform Gerrit API operations
                check_git_cookie_authdaemon_running()
            else:
                level = logging.WARNING

            logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=level,
                                datefmt='%Y-%m-%d %H:%M:%S')

            f(*args)
        return wrapped_preliminary_check
    return wrap_preliminary_check


def set_gcloud_project_config():
    """Sets project settings to chromeos-missing-patches project."""
    set_project_cmd = ['gcloud', 'config', 'set', 'project', 'google.com:chromeos-missing-patches']
    subprocess.run(set_project_cmd, stderr=subprocess.DEVNULL, check=True)


def cloud_sql_proxy_decorator(func):
    """Decorator for starting and stopping cloud_sql_proxy."""
    def cloud_sql_proxy_wrapper(*args, **kwargs):
        """Create cloud_sql_proxy process, run func, send signal.SIGKILL cloud_sql_proxy"""
        try:
            set_gcloud_project_config()
            sql_instance_cmd = ['gcloud', 'sql', 'instances', 'describe',
                                'linux-patches-mysql-8', '--format=value[](connectionName)']
            sql_instance = subprocess.check_output(sql_instance_cmd, encoding='utf-8').rstrip()

            cloudsql_cmd = ['cloud_sql_proxy', '-instances=%s=tcp:3306' % sql_instance]
            cloud_sql_proxy_pid = subprocess.Popen(cloudsql_cmd, stdout=subprocess.DEVNULL,
                                                    stderr=subprocess.DEVNULL)

            # Wait for cloud_sql_proxy to spin up
            # todo(hirthanan): read cloud_sql pipe to see when it starts up
            time.sleep(3)

            func(*args, **kwargs)

            cloud_sql_proxy_pid.kill()
        except subprocess.CalledProcessError:
            logging.error('Failed to retrieve sql_instance from gcloud')
            logging.error('User must be authenticated with Cloud SDK (run `gcloud auth login`)')
            logging.error('User must also be added to GCP project chromeos-missing-patches.')
            raise
    return cloud_sql_proxy_wrapper
