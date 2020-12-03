# -*- coding: utf-8 -*-
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Devserver module for handling update client requests."""

from __future__ import print_function

import os

from six.moves import urllib

import cherrypy  # pylint: disable=import-error

# TODO(crbug.com/872441): We try to import nebraska from different places
# because when we install the devserver, we copy the nebraska.py into the main
# directory. Once this bug is resolved, we can always import from nebraska
# directory.
try:
  from nebraska import nebraska
except ImportError:
  import nebraska

import setup_chromite  # pylint: disable=unused-import
from chromite.lib.xbuddy import cherrypy_log_util


# Module-local log function.
def _Log(message, *args):
  return cherrypy_log_util.LogWithTag('UPDATE', message, *args)

class AutoupdateError(Exception):
  """Exception classes used by this module."""
  pass


def _ChangeUrlPort(url, new_port):
  """Return the URL passed in with a different port"""
  scheme, netloc, path, query, fragment = urllib.parse.urlsplit(url)
  host_port = netloc.split(':')

  if len(host_port) == 1:
    host_port.append(new_port)
  else:
    host_port[1] = new_port

  print(host_port)
  netloc = '%s:%s' % tuple(host_port)

  # pylint: disable=too-many-function-args
  return urllib.parse.urlunsplit((scheme, netloc, path, query, fragment))

def _NonePathJoin(*args):
  """os.path.join that filters None's from the argument list."""
  return os.path.join(*[x for x in args if x is not None])


class Autoupdate(object):
  """Class that contains functionality that handles Chrome OS update pings."""

  def __init__(self, xbuddy, static_dir=None):
    """Initializes the class.

    Args:
      xbuddy: The xbuddy path.
      static_dir: The path to the devserver static directory.
    """
    self.xbuddy = xbuddy
    self.static_dir = static_dir

  def GetDevserverUrl(self):
    """Returns the devserver url base."""
    x_forwarded_host = cherrypy.request.headers.get('X-Forwarded-Host')
    if x_forwarded_host:
      # Select the left most <ip>:<port> value so that the request is
      # forwarded correctly.
      x_forwarded_host = [x.strip() for x in x_forwarded_host.split(',')][0]
      hostname = 'http://' + x_forwarded_host
    else:
      hostname = cherrypy.request.base

    return hostname

  def GetStaticUrl(self):
    """Returns the static url base that should prefix all payload responses."""
    hostname = self.GetDevserverUrl()
    _Log('Handling update ping as %s', hostname)

    static_urlbase = '%s/static' % hostname
    _Log('Using static url base %s', static_urlbase)
    return static_urlbase

  def GetPathToPayload(self, label, board):
    """Find a payload locally.

    See devserver's update rpc for documentation.

    Args:
      label: from update request
      board: from update request

    Returns:
      The relative path to an update from the static_dir

    Raises:
      AutoupdateError: If the update could not be found.
    """
    label = label or ''
    label_list = label.split('/')
    # There was no update found in the directory. Let XBuddy find the
    # payloads.
    if label_list[0] == 'xbuddy':
      # If path explicitly calls xbuddy, pop off the tag.
      label_list.pop()
    x_label, _ = self.xbuddy.Translate(label_list, board=board)
    # Path has been resolved, try to get the payload.
    return _NonePathJoin(self.static_dir, x_label)

  def HandleUpdatePing(self, data, label='', **kwargs):
    """Handles an update ping from an update client.

    Args:
      data: XML blob from client.
      label: optional label for the update.
      kwargs: The map of query strings passed to the /update API.

    Returns:
      Update payload message for client.
    """
    # Get the static url base that will form that base of our update url e.g.
    # http://hostname:8080/static/update.gz.
    static_urlbase = self.GetStaticUrl()
    # Change the URL's string query dictionary provided by cherrypy to a valid
    # dictionary that has proper values for its keys. e.g. True instead of
    # 'True'.
    kwargs = nebraska.QueryDictToDict(kwargs)

    # Process attributes of the update check.
    request = nebraska.Request(data)
    if request.request_type == nebraska.Request.RequestType.EVENT:
      _Log('A non-update event notification received. Returning an ack.')
      return nebraska.Nebraska().GetResponseToRequest(
          request, response_props=nebraska.ResponseProperties(**kwargs))

    _Log('Update Check Received.')

    try:
      path_to_payload = self.GetPathToPayload(label, request.board)
      base_url = _NonePathJoin(static_urlbase, path_to_payload)
      local_payload_dir = _NonePathJoin(self.static_dir, path_to_payload)
    except AutoupdateError as e:
      # Raised if we fail to generate an update payload.
      _Log('Failed to process an update request, but we will defer to '
           'nebraska to respond with no-update. The error was %s', e)

    _Log('Responding to client to use url %s to get image', base_url)
    nebraska_props = nebraska.NebraskaProperties(
        update_payloads_address=base_url,
        update_metadata_dir=local_payload_dir)
    nebraska_obj = nebraska.Nebraska(nebraska_props=nebraska_props)
    return nebraska_obj.GetResponseToRequest(
        request, response_props=nebraska.ResponseProperties(**kwargs))
