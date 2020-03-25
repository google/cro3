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
from chromite.lib.xbuddy import devserver_constants as constants


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

  def __init__(self, xbuddy, static_dir=None, proxy_port=None):
    """Initializes the class.

    Args:
      xbuddy: The xbuddy path.
      static_dir: The path to the devserver static directory.
      proxy_port: The port of local proxy to tell client to connect to you
        through.
    """
    self.xbuddy = xbuddy
    self.static_dir = static_dir
    self.proxy_port = proxy_port

  def GetUpdateForLabel(self, label):
    """Given a label, get an update from the directory.

    Args:
      label: the relative directory inside the static dir

    Returns:
      A relative path to the directory with the update payload.
      This is the label if an update did not need to be generated, but can
      be label/cache/hashed_dir_for_update.

    Raises:
      AutoupdateError: If client version is higher than available update found
        at the directory given by the label.
    """
    _Log('Update label: %s', label)
    static_update_path = _NonePathJoin(self.static_dir, label,
                                       constants.UPDATE_FILE)

    if label and os.path.exists(static_update_path):
      # An update payload was found for the given label, return it.
      return label

    # The label didn't resolve.
    _Log('Did not found any update payload for label %s.', label)
    return None

  def GetDevserverUrl(self):
    """Returns the devserver url base."""
    x_forwarded_host = cherrypy.request.headers.get('X-Forwarded-Host')
    if x_forwarded_host:
      hostname = 'http://' + x_forwarded_host
    else:
      hostname = cherrypy.request.base

    return hostname

  def GetStaticUrl(self):
    """Returns the static url base that should prefix all payload responses."""
    hostname = self.GetDevserverUrl()

    static_urlbase = '%s/static' % hostname
    # If we have a proxy port, adjust the URL we instruct the client to
    # use to go through the proxy.
    if self.proxy_port:
      static_urlbase = _ChangeUrlPort(static_urlbase, self.proxy_port)

    _Log('Using static url base %s', static_urlbase)
    _Log('Handling update ping as %s', hostname)
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
    # Suppose that the path follows old protocol of indexing straight
    # into static_dir with board/version label.
    # Attempt to get the update in that directory, generating if necc.
    path_to_payload = self.GetUpdateForLabel(label)
    if path_to_payload is None:
      # There was no update found in the directory. Let XBuddy find the
      # payloads.
      if label_list[0] == 'xbuddy':
        # If path explicitly calls xbuddy, pop off the tag.
        label_list.pop()
      x_label, _ = self.xbuddy.Translate(label_list, board=board)
      # Path has been resolved, try to get the payload.
      path_to_payload = self.GetUpdateForLabel(x_label)
      if path_to_payload is None:
        # No update payload found after translation. Try to get an update to
        # a test image from GS using the label.
        path_to_payload, _image_name = self.xbuddy.Get(
            ['remote', label, 'full_payload'])

    # One of the above options should have gotten us a relative path.
    if path_to_payload is None:
      raise AutoupdateError('Failed to get an update for: %s' % label)

    return path_to_payload

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
