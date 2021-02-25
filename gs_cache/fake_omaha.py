# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An cherry app to play as a fake Omaha service.

This is a short term solution in order to deprecation devserver.py from labs.
"""
from __future__ import print_function

import cherrypy  # pylint: disable=import-error
import nebraska_wrapper


def get_config():
  """Get cherrypy config for this application."""
  return {
      '/': {
          'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
      }
  }


@cherrypy.expose
class FakeOmaha(object):
  """An application to handle fake Omaha requests."""
  def POST(self, *args, **kwargs):
    """A URL handler to handle update check ping."""
    label = '/'.join(args)
    full_update = kwargs.pop('full_payload', 'unspecified')
    server_addr, _ = cherrypy.request.headers.get('X-Forwarded-Host').split(':')
    body_length = int(cherrypy.request.headers.get('Content-Length', 0))
    data = cherrypy.request.rfile.read(body_length)
    with nebraska_wrapper.NebraskaWrapper(label, server_addr,
                                          full_update) as nb:
      return nb.HandleUpdatePing(data, **kwargs)
