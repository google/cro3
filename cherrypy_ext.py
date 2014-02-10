#!/usr/bin/python

# Copyright (c) 2014 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Extensions for CherryPy.

This module contains patches and add-ons for the stock CherryPy distribution.
Everything in here is compatible with the CherryPy version used in the chroot,
as well as the recent stable version as used (for example) in the lab. This
premise is verified by the corresponding unit tests.
"""

import cherrypy
import os


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
    with open(self.portfile, "wb") as f:
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
      except:
        self.bus.log('Failed to remove port file: %r.' % self.portfile)


class ZeroPortPatcher(object):
  """Patches a CherryPy module to support binding to any available port."""

  # The cached value of the actual port bound by the HTTP server.
  cached_port = 0

  @classmethod
  def _WrapWaitForPort(cls, cherrypy_module, func_name, use_cached):
    """Ensures that a port is not zero before calling a wait-for-port function.

    This wraps stock CherryPy module-level functions that wait for a port to be
    free/occupied with a conditional that ensures the port argument isn't zero.
    Prior to that, the wrapper attempts to pull the actual bound port number
    from CherryPy's underlying HTTP server, if present. In this case, it'll
    also cache the pulled out value, so it can be used in subsequent calls; one
    such scenario is checking when a previously bound (actual) port has been
    released after server shutdown.  This makes those functions do their
    intended job when the server is configured to bind to an arbitrary
    available port (server.socket_port is zero), a necessary feature.

    Raises:
      AttributeError: if func_name is not an attribute of cherrypy_module.
    """
    module = cherrypy_module.process.servers
    func = getattr(module, func_name)  # Will fail if not present.

    def wrapped_func(host, port):
      if not port:
        actual_port = PortFile.get_port_from_httpserver()
        if use_cached:
          port = cls.cached_port
          using = 'cached'
        else:
          port = actual_port
          using = 'actual'

        if port:
          cherrypy_module.engine.log('(%s) Waiting for %s port %s.' %
                                     (func_name, using, port))
        else:
          cherrypy_module.engine.log('(%s) No %s port to wait for.' %
                                     (func_name, using))

        cls.cached_port = port

      if port:
        return func(host, port)

    setattr(module, func_name, wrapped_func)

  @classmethod
  def DoPatch(cls, cherrypy_module):
    """Patches a given CherryPy module.

    Raises:
      AttributeError: when fails to patch CherryPy.
    """
    cls._WrapWaitForPort(cherrypy_module, 'wait_for_free_port', True)
    cls._WrapWaitForPort(cherrypy_module, 'wait_for_occupied_port', False)
