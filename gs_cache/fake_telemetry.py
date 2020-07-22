# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""An cherry app to play as a fake Telemetry service.

This is a short term solution in order to deprecation devserver.py from labs.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import cherrypy  # pylint: disable=import-error
import telemetry_setup


def get_config():
  """Get cherrypy config for this application."""
  return {
      '/': {
          'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
      }
  }


@cherrypy.expose
class FakeTelemetry(object):
  """An application to handle fake telemetry requests."""
  def GET(self, **kwargs):
    """A URL handler for setting up telemetry."""
    archive_url = kwargs.get('archive_url')
    with telemetry_setup.TelemetrySetup(archive_url) as tlm:
      return tlm.Setup()
