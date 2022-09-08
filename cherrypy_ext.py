# -*- coding: utf-8 -*-
# Copyright 2014 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Extensions for CherryPy.

This module contains patches and add-ons for the stock CherryPy distribution.
Everything in here is compatible with the CherryPy version used in the chroot,
as well as the recent stable version as used (for example) in the lab. This
premise is verified by the corresponding unit tests.
"""

from __future__ import print_function

import os

import cherrypy  # pylint: disable=import-error


class PortFile(cherrypy.process.plugins.SimplePlugin):
  """CherryPy plugin for maintaining a port file via a WSPBus.

  This is a hack, because we're using arbitrary bus signals (like 'start' and
  'log') to trigger checking whether the server has already bound the listening
  socket to a port, in which case we write it to a file. It would work as long
  as the server (for example) logs the fact that it is up and serving *after*
  it has bound the port, which happens to be the case. The upside is that we
  don't have to use ad hoc signals, nor do we need to change the implementaiton
  of various CherryPy classes (like ServerAdapter) to use such signals.

  In all other respects, this plugin mirrors the behavior of the stock
  cherrypy.process.plugins.PIDFile plugin. Note that it will not work correctly
  in the presence of multiple server threads, nor is it meant to; it will only
  write the port of the main server instance (cherrypy.server), if present.
  """

  def __init__(self, bus, portfile):
    super(PortFile, self).__init__(bus)
    self.portfile = portfile
    self.stopped = True
    self.written = False

  @staticmethod
  def get_port_from_httpserver():
    """Pulls the actual bound port number from CherryPy's HTTP server.

    This assumes that cherrypy.server is the main server instance,
    cherrypy.server.httpserver the underlying HTTP server, and
    cherrypy.server.httpserver.socket the socket used for serving. These appear
    to be well accepted conventions throughout recent versions of CherryPy.

    Returns:
      The actual bound port; zero if not bound or could not be retrieved.
    """
    server_socket = (getattr(cherrypy.server, 'httpserver', None) and
                     getattr(cherrypy.server.httpserver, 'socket', None))
    bind_addr = server_socket and server_socket.getsockname()
    return bind_addr[1] if (bind_addr and isinstance(bind_addr, tuple)) else 0

  def _check_and_write_port(self):
    """Check if a port has been bound, and if so write it to file.

    This maintains a flag to denote whether or not the server has started (to
    avoid doing unnecessary work) and another flag denoting whether a port was
    already written to file (so it can be removed upon 'stop').

    IMPORTANT: to avoid infinite recursion, do not emit any bus event (e.g.
    self.bus.log()) until after setting self.written to True!
    """
    if self.stopped or self.written:
      return
    port = self.get_port_from_httpserver()
    if not port:
      return
    with open(self.portfile, 'w') as f:
      f.write(str(port))
    self.written = True
    self.bus.log('Port %r written to %r.' % (port, self.portfile))

  def start(self):
    self.stopped = False
    self._check_and_write_port()
  start.priority = 50

  def log(self, _msg, _level):
    self._check_and_write_port()

  def stop(self):
    """Removes the port file.

    IMPORTANT: to avoid re-writing the port file via other signals (e.g.
    self.bus.log()) be sure to set self.stopped to True before setting
    self.written to False!
    """
    self.stopped = True
    if self.written:
      self.written = False
      try:
        os.remove(self.portfile)
        self.bus.log('Port file removed: %r.' % self.portfile)
      except (KeyboardInterrupt, SystemExit):
        raise
      except Exception:
        self.bus.log('Failed to remove port file: %r.' % self.portfile)
