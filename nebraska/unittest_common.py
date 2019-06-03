#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common utilities for Nebraska/Tonka unittests"""

from __future__ import print_function

from xml.etree import ElementTree

import nebraska

def GenerateAppData(appid='foo', name='foobar', is_delta=False,
                    target_version='2.0.0', source_version=None):
  """Generates an AppData test instance."""
  data = {
      nebraska.AppIndex.AppData.APPID_KEY: appid,
      nebraska.AppIndex.AppData.NAME_KEY: name,
      nebraska.AppIndex.AppData.TARGET_VERSION_KEY: target_version,
      nebraska.AppIndex.AppData.IS_DELTA_KEY: is_delta,
      nebraska.AppIndex.AppData.SOURCE_VERSION_KEY: source_version,
      nebraska.AppIndex.AppData.SIZE_KEY: '9001',
      nebraska.AppIndex.AppData.METADATA_SIG_KEY: \
          'Dr4RFXYgcfvFHV/0VRQs+SCQmz15Sk04LLEDswtvng8BqNbBXA7VvPUhpCgX5T/t7cwP'
          'xTUHJVtxIREuBZpyIQxJQFZATspaClelpKBwadQzj7dpfShLpcbdlfM8qbLjIbXfC2Vy'
          'mw03Mwf38lm0Fm75SANSTW9S4arPDf3sy9YGuqesnEJXyT3ZSGyK+Xto79zlURUXCgmi'
          'a6t7MaJE3ZbCdeF4EiEMPDsipqj9ggmKwiCdUl2+RxTznX/015XFiBhogLrx9RCPHTR8'
          'nLz0H9RcRhIvMd+8g4kHUZTDvjCvG5EZHpIKk8FK8z0zY/LWVr738evwuNNwyKIazkQB'
          'TA==',
      nebraska.AppIndex.AppData.METADATA_SIZE_KEY: '42',
      nebraska.AppIndex.AppData.SHA256_HEX_KEY: \
          '886fd274745b4fa8d1f253cff11242fac07a29522b1bb9e028ab1480353d3160'
  }
  return nebraska.AppIndex.AppData(data)

def GenerateAppRequest(request_type=nebraska.Request.RequestType.UPDATE,
                       appid='foo', version='1.0.0', delta_okay=False,
                       event=False, event_type='1', event_result='1',
                       update_check=True, ping=False):
  """Generates an app request test instance."""
  APP_TEMPLATE = """<app appid="" version="" delta_okay=""
hardware_class="foo-hardware" track="foo-channel" board="foo-board"> </app>"""
  PING_TEMPLATE = """<ping active="1" a="1" r="1"></ping>"""
  UPDATE_CHECK_TEMPLATE = """<updatecheck></updatecheck>"""
  EVENT_TEMPLATE = """<event eventtype="3" eventresult="1"></event>"""

  app = ElementTree.fromstring(APP_TEMPLATE)
  app.set('appid', appid)
  app.set('version', version)
  app.set('delta_okay', 'true' if delta_okay else 'false')

  if ping:
    app.append(ElementTree.fromstring(PING_TEMPLATE))
  if update_check:
    app.append(ElementTree.fromstring(UPDATE_CHECK_TEMPLATE))
  if event:
    event_tag = ElementTree.fromstring(EVENT_TEMPLATE)
    event_tag.set('eventtype', event_type)
    event_tag.set('eventresult', event_result)
    app.append(event_tag)

  return nebraska.Request.AppRequest(app, request_type)
