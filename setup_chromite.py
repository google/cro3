# Copyright (c) 2016 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Set up syspath to import chromite."""

from __future__ import print_function

import os
import sys

# Make sure that chromite is available to import.
_path = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                     os.pardir)
if _path not in sys.path:
  sys.path.insert(0, os.path.abspath(_path))

del _path
