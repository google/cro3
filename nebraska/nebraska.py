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

    self.send_error(500, request_str)


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
