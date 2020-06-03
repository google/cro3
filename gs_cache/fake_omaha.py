# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An cherry app to play as a fake Omaha service.

This is a short term solution in order to deprecation devserver.py from labs.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import cherrypy


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
    body_length = int(cherrypy.request.headers.get('Content-Length', 0))
    data = cherrypy.request.rfile.read(body_length)
    return 'Fake Omaha: To be implemented\nArgs: %s\nkwargs: %s\nData: %s\n' % (
        args, kwargs, data)
