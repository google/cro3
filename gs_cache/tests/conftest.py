# Copyright 2018 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The configuration python file for Pytest.

In this file, we add below customized command line option:
  --network: Run tests that depend on good netowrk connectivity.
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import pytest


def pytest_addoption(parser):
  parser.addoption("--network", action="store_true", default=False,
                   help="Run tests that depend on good network connectivity")


def pytest_collection_modifyitems(config, items):
  if config.getoption("--network"):
    # run network tests
    return
  skip_network_tests = pytest.mark.skip(
      reason="Skipping network test (re-run w/--network)")
  for item in items:
    if "network" in item.keywords:
      item.add_marker(skip_network_tests)
