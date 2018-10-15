#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common utilities for Nebraska/Tonka unittests"""

from __future__ import print_function

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
    self.headers = None
    self.rfile = None

def NebraskaGenerator(source_dir, target_dir, port):
  """Generates a Nebraska server instance."""
  return NebraskaServer(source_dir, target_dir, port)


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
      AppData.IS_DELTA_KEY: is_delta,
      AppData.SIZE_KEY: '9001',
      AppData.MD5_HASH_KEY: '0xc0ffee',
      AppData.METADATA_SIG_KEY: '0xcafefood',
      AppData.METADATA_SIZE_KEY: '42',
      AppData.SHA1_HASH_KEY: '0x1337c0de',
      AppData.SHA256_HASH_KEY: '0xdeadbeef',
      AppData.VERSION_KEY: version,
      AppData.SRC_VERSION_KEY: src_version
  }
