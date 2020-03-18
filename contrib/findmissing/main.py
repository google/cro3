#!/usr/bin/env python3
# -*- coding: utf-8 -*-"
#
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Web server performing operations on our systems.

Systems will include: Cloud Scheduler, CloudSQL, and Compute Engine
"""

from __future__ import print_function

import synchronize
import missing

def home():
    """Test route for status check on compute engine"""
    return 'hello, compute engine are you there?\n'

def sync_repositories_and_databases():
    """Synchronizes state of repositories, databases, and missing patches."""
    synchronize.synchronize_repositories()
    synchronize.synchronize_databases()

def create_new_patches():
    """Creates up to number of new patches in gerrit."""
    missing.new_missing_patches()

def update_patches():
    """Updates fixes table entries on regular basis."""
    missing.update_missing_patches()
