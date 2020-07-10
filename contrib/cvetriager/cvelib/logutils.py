# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for assisting with logging."""
from __future__ import print_function

import logging

loggers = {}
LOGFMT = '%(process)d:%(levelname)s:%(name)s:%(message)s'


def setuplogging(loglvl, name):
    """Creates and returns a logger object."""
    if name not in loggers:
        logger = logging.getLogger(name)
        formatter = logging.Formatter(LOGFMT)
        sh = logging.StreamHandler()
        sh.setFormatter(formatter)
        sh.setLevel(loglvl)
        logger.addHandler(sh)
        logger.setLevel(loglvl)
        loggers[name] = logger
    return loggers[name]
