#!/usr/bin/env python3
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""This module contains shared helper functions for gfx scripts"""

from __future__ import print_function

import sys
import traceback


def panic(msg: str, exit_code: int = 1):
  """Exits the process with message and error code

  Dumps error message along with callstack and exits the application with
  specified exit code
  """
  print('-' * 60, file=sys.stderr)
  print('ERROR: %s' % msg, file=sys.stderr)
  print('-' * 60, file=sys.stderr)
  traceback.print_exc(file=sys.stderr)
  print('-' * 60, file=sys.stderr)
  sys.exit(exit_code)
