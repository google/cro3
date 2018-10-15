#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common utilities for Nebraska/Tonka unittests"""

from __future__ import print_function

import nebraska


class NebraskaHandler(nebraska.NebraskaHandler):
  """Subclass NebraskaHandler to facilitate testing.

  Because of the complexity of the socket handling super class init functions,
  the easiest way to test NebraskaHandler is to just subclass it and mock
  whatever we need from its super classes.
  """
  # pylint: disable=super-init-not-called
  def __init__(self):
    self.headers = None
    self.rfile = None


def NebraskaGenerator(port):
  """Generates a Nebraska server instance."""
  return nebraska.NebraskaServer(port)
