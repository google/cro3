# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Logging via CherryPy."""

import re

import cherrypy


class Loggable(object):
  """Provides a log method, with automatic log tag generation."""
  _CAMELCASE_RE = re.compile('(?<=.)([A-Z])')

  def _Log(self, message, *args, **kwargs):
    return LogWithTag(
        self._CAMELCASE_RE.sub(r'_\1', self.__class__.__name__).upper(),
        message, *args, **kwargs)


def LogWithTag(tag, message, *args, **kwargs):
  # CherryPy log doesn't seem to take any optional args, so we'll just join
  # them into a single string, if any are provided.
  return cherrypy.log(message + ((' ' + ' '.join(args)) if args else ''), tag)
