#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common utilities for Nebraska/Tonka unittests"""

from __future__ import print_function

import nebraska

def AppDataGenerator(appid, is_delta, target_version, source_version):
  """Generates and AppData test instance."""
  return nebraska.AppData(
      GenAppJson(appid=appid, is_delta=is_delta, target_version=target_version,
                 source_version=source_version))


def GenAppJson(appid='appid_foo', name='foobar', is_delta='False',
               target_version="2.0.0", source_version="1.0.0"):
  """Mocks JSON parsing functionality for testing."""
  return {
      nebraska.AppData.APPID_KEY: appid,
      nebraska.AppData.NAME_KEY: name,
      nebraska.AppData.TARGET_VERSION_KEY: target_version,
      nebraska.AppData.IS_DELTA_KEY: is_delta,
      nebraska.AppData.SOURCE_VERSION_KEY: source_version,
      nebraska.AppData.SIZE_KEY: '9001',
      nebraska.AppData.METADATA_SIG_KEY: \
          'Dr4RFXYgcfvFHV/0VRQs+SCQmz15Sk04LLEDswtvng8BqNbBXA7VvPUhpCgX5T/t7cwP'
          'xTUHJVtxIREuBZpyIQxJQFZATspaClelpKBwadQzj7dpfShLpcbdlfM8qbLjIbXfC2Vy'
          'mw03Mwf38lm0Fm75SANSTW9S4arPDf3sy9YGuqesnEJXyT3ZSGyK+Xto79zlURUXCgmi'
          'a6t7MaJE3ZbCdeF4EiEMPDsipqj9ggmKwiCdUl2+RxTznX/015XFiBhogLrx9RCPHTR8'
          'nLz0H9RcRhIvMd+8g4kHUZTDvjCvG5EZHpIKk8FK8z0zY/LWVr738evwuNNwyKIazkQB'
          'TA==',
      nebraska.AppData.METADATA_SIZE_KEY: '42',
      nebraska.AppData.SHA256_HEX_KEY: '886fd274745b4fa8d1f253cff11242fac07a295'
                                       '22b1bb9e028ab1480353d3160'
  }
