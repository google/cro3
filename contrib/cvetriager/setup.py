# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Setup for CVE Triager tool."""

from __future__ import print_function
from setuptools import setup

setup(
    name='cvetriage',
    version='1.0',
    description='Triage tool for bugs against Chromium OS',
    author='Wanda Mora',
    author_email='morawand@chromium.org',
    license='BSD-Google',
    packages=['cvelib'],
    zip_safe=False,
    install_requires=['bs4', 'requests'],
    test_suite='tests',
)
