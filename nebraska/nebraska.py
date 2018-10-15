#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Mock Omaha server"""

from __future__ import print_function

# pylint: disable=cros-logging-import
import argparse
import logging
import sys
import threading

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from enum import Enum
from xml.etree import ElementTree


class Request(object):
  """Request consisting of a list of apps to update/install."""

  APP_TAG = 'app'
  APPID_ATTR = 'appid'
  VERSION_ATTR = 'version'
  DELTA_OKAY_ATTR = 'delta_okay'
  HW_CLASS_ATTR = 'hardware_class'
  UPDATE_CHECK_TAG = 'updatecheck'
  PING_TAG = 'ping'
  EVENT_TAG = 'event'
  EVENT_TYPE_ATTR = 'eventtype'
  EVENT_RESULT_ATTR = 'eventresult'

  def __init__(self, request_str):
    """Initializes a request instance.

    Args:
      request_str: XML-formatted request string.
    """
    self.request_str = request_str

  def ParseRequest(self):
    """Parse an XML request string into a list of app requests.

    An app request can be a no-op, an install request, or an update request, and
    may include a ping and/or event tag. We treat app requests with the update
    tag omitted as no-ops, since the server is not required to return payload
    information. Install requests are signalled by sending app requests along
    with a no-op request for the platform app.

    Returns:
      A list of AppRequest instances.

    Raises:
      ValueError if the request string is not a valid XML request.
    """
    try:
      request_root = ElementTree.fromstring(self.request_str)
    except ElementTree.ParseError as err:
      logging.error("Request string is not valid XML (%s)", str(err))
      raise ValueError

    # An install is signalled by omitting the update check for the platform
    # app, which can be found based on the presense of a hardware_class tag,
    # which is absent on DLC update and install requests.
    platform_app = next(iter([x for x in request_root.findall(self.APP_TAG) if
                              x.get(self.HW_CLASS_ATTR) is not None]), None)
    if platform_app is not None:
      is_install = platform_app.find(self.UPDATE_CHECK_TAG) is None
    else:
      is_install = False

    app_requests = []
    for app in request_root.findall(self.APP_TAG):
      appid = app.get(self.APPID_ATTR)
      version = app.get(self.VERSION_ATTR)
      delta_okay = app.get(self.DELTA_OKAY_ATTR) == "true"

      event = app.find(self.EVENT_TAG)
      if event is not None:
        event_type = event.get(self.EVENT_TYPE_ATTR)
        event_result = event.get(self.EVENT_RESULT_ATTR, 0)
      else:
        event_type = None
        event_result = None

      ping = app.find(self.PING_TAG) is not None

      if app.find(self.UPDATE_CHECK_TAG) is not None:
        if is_install:
          request_type = Request.AppRequest.RequestType.INSTALL
        else:
          request_type = Request.AppRequest.RequestType.UPDATE
      else:
        request_type = Request.AppRequest.RequestType.NO_OP

      app_request = Request.AppRequest(
          request_type=request_type,
          appid=appid,
          ping=ping,
          version=version,
          delta_okay=delta_okay,
          event_type=event_type,
          event_result=event_result)

      if not app_request.IsValid():
        raise ValueError("Invalid request: %s", str(app_request))

      app_requests.append(app_request)

    return app_requests

  class AppRequest(object):
    """An app request.

    Can be an update request, install request, or neither if the update check
    tag is omitted (i.e. the platform app when installing a DLC, or when a
    request is only an event), in which case we treat the request as a no-op.
    An app request can also send pings and event result information.
    """

    RequestType = Enum("RequestType", "INSTALL UPDATE NO_OP")

    def __init__(self, request_type, appid, ping=False, version=None,
                 delta_okay=None, event_type=None, event_result=None):
      """Initializes a Request.

      Args:
        request_type: install, update, or no-op.
        appid: The requested appid.
        ping: True if the server should respond to a ping.
        version: Current Chrome OS version.
        delta_okay: True if an update request can accept a delta update.
        event_type: Type of event.
        event_result: Event result.

        More on event pings:
        https://github.com/google/omaha/blob/master/doc/ServerProtocolV3.md
      """
      self.request_type = request_type
      self.appid = appid
      self.ping = ping
      self.version = version
      self.delta_okay = delta_okay
      self.event_type = event_type
      self.event_result = event_result

    def __str__(self):
      """Returns a string representation of an AppRequest."""
      if self.request_type == self.RequestType.NO_OP:
        return "{}".format(self.appid)
      elif self.request_type == self.RequestType.INSTALL:
        return "install {} v{}".format(self.appid, self.version)
      elif self.request_type == self.RequestType.UPDATE:
        return "{} update {} from v{}".format(
            "delta" if self.delta_okay else "full", self.appid, self.version)

    def IsValid(self):
      """Returns true if an AppRequest is valid, False otherwise."""
      return None not in (self.request_type, self.appid, self.version)


class NebraskaHandler(BaseHTTPRequestHandler):
  """HTTP request handler for Omaha requests."""

  def GetRequestString(self):
    """Extracts the request string from an HTML POST request"""
    request_len = int(self.headers.getheader('content-length'))
    return self.rfile.read(request_len)

  def do_POST(self):
    """Responds to XML-formatted Omaha requests."""
    request_str = self.GetRequestString()
    logging.debug("Received request: %s", request_str)

    request = Request(request_str)
    try:
      for app in request.ParseRequest():
        logging.debug("Received request: %s", str(app))
    except ValueError:
      self.send_error(400, "Invalid update or install request")
      return

    self.send_error(500, "Not implemented!")


class NebraskaServer(object):
  """A simple Omaha server instance.

  A simple mock of an Omaha server. Responds to XML-formatted install/update
  requests based on the contents of metadata files in source and target
  directories, respectively. These metadata files are used to configure
  responses to Omaha requests from Update Engine.
  """

  def __init__(self, port=0):
    """Initializes a server instance.

    Args:
      port: Port the server should run on, 0 if the OS should assign a port.
    """
    self._port = port
    self._httpd = None
    self._server_thread = None

  def Start(self):
    """Starts a mock Omaha HTTP server."""
    self._httpd = HTTPServer(('', self.Port()), NebraskaHandler)
    self._port = self._httpd.server_port
    self._httpd.owner = self
    self._server_thread = threading.Thread(target=self._httpd.serve_forever)
    self._server_thread.start()

  def Stop(self):
    """Stops the mock Omaha server."""
    self._httpd.shutdown()
    self._server_thread.join()

  def Port(self):
    """Returns the server's port."""
    return self._port


def ParseArguments(argv):
  """Parses command line arguments.

  Args:
    argv: List of commandline arguments

  Returns:
    Namespace object containing parsed arguments
  """
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--port', metavar='PORT', type=int, default=0,
                      help='Port to run the server on')
  return parser.parse_args(argv[1:])


def main(argv):
  logging.basicConfig(level=logging.DEBUG)
  opts = ParseArguments(argv)

  nebraska = NebraskaServer(port=opts.port)

  nebraska.Start()
  logging.info("Running on port %d. Press 'q' to quit.", nebraska.Port())

  try:
    while raw_input() != 'q':
      pass
  except(EOFError, KeyboardInterrupt, SystemExit):
    pass

  logging.info("Exiting...")
  nebraska.Stop()


if __name__ == "__main__":
  sys.exit(main(sys.argv))
