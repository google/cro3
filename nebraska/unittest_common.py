#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common utilities for Nebraska/Tonka unittests"""

from __future__ import print_function

import mock

from nebraska import AppData, NebraskaServer, \
                     NebraskaHandler as RealNebraskaHandler


class NebraskaHandler(RealNebraskaHandler):
  """Subclass NebraskaHandler to facilitate testing.

  Because of the complexity of the socket handling super class init functions,
  the easiest way to test NebraskaHandler is to just subclass it and mock
  whatever we need from its super classes.
  """
  # pylint: disable=super-init-not-called
  def __init__(self):
    self.headers = mock.MagicMock()
    self.send_response = mock.MagicMock()
    self.send_error = mock.MagicMock()
    self.send_header = mock.MagicMock()
    self.end_headers = mock.MagicMock()
    self.rfile = mock.MagicMock()
    self.wfile = mock.MagicMock()
    self.server = mock.MagicMock()


def NebraskaGenerator(source_dir, target_dir, payload_addr, port):
  """Generates a Nebraska server instance."""
  return NebraskaServer(source_dir, target_dir, payload_addr, port)


def AppDataGenerator(appid, is_delta, version, src_version):
  """Generates and AppData test instance."""
  return AppData(
      GenAppJson(appid=appid, is_delta=is_delta, version=version,
                 src_version=src_version))


def GenAppJson(appid='appid_foo', name='foobar', is_delta='False',
               version="2.0.0", src_version="1.0.0"):
  """Mocks JSON parsing functionality for testing."""
  return {
      AppData.APPID_KEY: appid,
      AppData.NAME_KEY: name,
      AppData.VERSION_KEY: version,
      AppData.IS_DELTA_KEY: is_delta,
      AppData.SRC_VERSION_KEY: src_version,
      AppData.SIZE_KEY: '9001',
      AppData.METADATA_SIG_KEY: \
          'Dr4RFXYgcfvFHV/0VRQs+SCQmz15Sk04LLEDswtvng8BqNbBXA7VvPUhpCgX5T/t7cwP'
          'xTUHJVtxIREuBZpyIQxJQFZATspaClelpKBwadQzj7dpfShLpcbdlfM8qbLjIbXfC2Vy'
          'mw03Mwf38lm0Fm75SANSTW9S4arPDf3sy9YGuqesnEJXyT3ZSGyK+Xto79zlURUXCgmi'
          'a6t7MaJE3ZbCdeF4EiEMPDsipqj9ggmKwiCdUl2+RxTznX/015XFiBhogLrx9RCPHTR8'
          'nLz0H9RcRhIvMd+8g4kHUZTDvjCvG5EZHpIKk8FK8z0zY/LWVr738evwuNNwyKIazkQB'
          'TA==',
      AppData.METADATA_SIZE_KEY: '42',
      AppData.SHA256_HASH_KEY: "886fd274745b4fa8d1f253cff11242fac07a29522b1bb9e"
                               "028ab1480353d3160"
  }
