# -*-coding: utf-8 -*-

"""Setup for CVE Triager tool"""

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
    test_suite='tests',
)
