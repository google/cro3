# -*- coding: utf-8 -*-
# Copyright 2019 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""This module defines all exceptions used by DevServer."""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function


class DevServerError(Exception):
  """Exception class used by DevServer."""
