#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tests for request string parsing."""

from __future__ import print_function

import unittest

import nebraska


class XMLStrings(object):
  """Collection of XML request strings for testing."""

  INSTALL_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" hardware_class="c" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
  </app>
  <app appid="foo" version="1.0.0" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
  <app appid="bar" version="1.0.0" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
</request>
"""

  UPDATE_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" hardware_class="c" delta_okay="true">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
  <app appid="foo" version="1.0.0" delta_okay="true">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
  <app appid="bar" version="1.0.0" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
</request>
"""

  INVALID_NOOP_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" hardware_class="c" delta_okay="true">
    <ping active="1" a="1" r="1"></ping>
  </app>
  <app appid="foo" version="1.0.0" delta_okay="true">
    <ping active="1" a="1" r="1"></ping>
  </app>
  <app appid="bar" version="1.0.0" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
</request>
"""

  EVENT_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" hardware_class="c">
    <event eventtype="3" eventresult="1"></event>
  </app>
</request>
"""

  INVALID_XML_REQUEST = """invalid xml!
<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="foo" version="1.0.0" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
  </app>
</request>
"""

  # No appid
  INVALID_APP_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app version="1.0.0" hardware_class="caroline" delta_okay="true">
    <ping active="1" a="1" r="1"></ping>
  </app>
</request>
"""

  # No version number
  INVALID_INSTALL_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0">
  <os version="Indy" platform="Chrome OS" sp="10323.52.0_x86_64"></os>
  <app appid="platform" version="1.0.0" hardware_class="c" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
  </app>
  <app appid="foo" delta_okay="false">
    <ping active="1" a="1" r="1"></ping>
    <updatecheck targetversionprefix=""></updatecheck>
  </app>
</request>
"""

class RequestTest(unittest.TestCase):
  """Tests for Request class."""

  def testParseRequestInvalidXML(self):
    """Tests ParseRequest handling of invalid XML."""
    with self.assertRaises(nebraska.NebraskaErrorInvalidRequest):
      request = nebraska.Request(XMLStrings.INVALID_XML_REQUEST)
      request.ParseRequest()

  def testParseRequestInvalidApp(self):
    """Tests ParseRequest handling of invalid app requests."""
    with self.assertRaises(nebraska.NebraskaErrorInvalidRequest):
      request = nebraska.Request(XMLStrings.INVALID_APP_REQUEST)
      request.ParseRequest()

  def testParseRequestInvalidInstall(self):
    """Tests ParseRequest handling of invalid app requests."""
    with self.assertRaises(nebraska.NebraskaErrorInvalidRequest):
      request = nebraska.Request(XMLStrings.INVALID_INSTALL_REQUEST)
      request.ParseRequest()

  def testParseRequestInvalidNoop(self):
    """Tests ParseRequest handling of invalid mixed no-op request."""
    with self.assertRaises(nebraska.NebraskaErrorInvalidRequest):
      request = nebraska.Request(XMLStrings.INVALID_NOOP_REQUEST)
      request.ParseRequest()

  def testParseRequestInstall(self):
    """Tests ParseRequest handling of install requests."""
    request = nebraska.Request(XMLStrings.INSTALL_REQUEST)
    app_requests = request.ParseRequest()

    self.assertTrue(app_requests[0].request_type ==
                    nebraska.Request.AppRequest.RequestType.NO_OP)
    self.assertTrue(app_requests[1].request_type ==
                    nebraska.Request.AppRequest.RequestType.INSTALL)
    self.assertTrue(app_requests[2].request_type ==
                    nebraska.Request.AppRequest.RequestType.INSTALL)

    self.assertTrue(app_requests[0].appid == "platform")
    self.assertTrue(app_requests[1].appid == "foo")
    self.assertTrue(app_requests[2].appid == "bar")

    self.assertTrue(app_requests[1].version == "1.0.0")
    self.assertTrue(app_requests[2].version == "1.0.0")

  def testParseRequestUpdate(self):
    """Tests ParseRequest handling of update requests."""
    request = nebraska.Request(XMLStrings.UPDATE_REQUEST)
    app_requests = request.ParseRequest()

    self.assertTrue(app_requests[0].request_type ==
                    nebraska.Request.AppRequest.RequestType.UPDATE)
    self.assertTrue(app_requests[1].request_type ==
                    nebraska.Request.AppRequest.RequestType.UPDATE)
    self.assertTrue(app_requests[2].request_type ==
                    nebraska.Request.AppRequest.RequestType.UPDATE)

    self.assertTrue(app_requests[0].appid == "platform")
    self.assertTrue(app_requests[1].appid == "foo")
    self.assertTrue(app_requests[2].appid == "bar")

    self.assertTrue(app_requests[0].version == "1.0.0")
    self.assertTrue(app_requests[1].version == "1.0.0")
    self.assertTrue(app_requests[2].version == "1.0.0")

    self.assertTrue(app_requests[0].delta_okay)
    self.assertTrue(app_requests[1].delta_okay)
    self.assertFalse(app_requests[2].delta_okay)

  def testParseRequestEventPing(self):
    """Tests ParseRequest handling of event ping requests."""
    request = nebraska.Request(XMLStrings.EVENT_REQUEST)
    app_requests = request.ParseRequest()

    self.assertTrue(app_requests[0].request_type ==
                    nebraska.Request.AppRequest.RequestType.NO_OP)
    self.assertTrue(app_requests[0].appid == "platform")
    self.assertTrue(app_requests[0].event_type == "3")
    self.assertTrue(app_requests[0].event_result == "1")


if __name__ == '__main__':
  unittest.main()
