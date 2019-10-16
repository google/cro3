# -*- coding: utf-8 -*-
# Copyright (c) 2011 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Devserver module for handling update client requests."""

from __future__ import print_function

import json
import os
import threading
import time

from six.moves import urllib

import cherrypy  # pylint: disable=import-error

import build_util
import common_util
import devserver_constants as constants
import log_util

# TODO(crbug.com/872441): We try to import nebraska from different places
# because when we install the devserver, we copy the nebraska.py into the main
# directory. Once this bug is resolved, we can always import from nebraska
# directory.
try:
  from nebraska import nebraska
except ImportError:
  import nebraska


# Module-local log function.
def _Log(message, *args):
  return log_util.LogWithTag('UPDATE', message, *args)


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


class HostInfo(object):
  """Records information about an individual host.

  Attributes:
    attrs: Static attributes (legacy)
    log: Complete log of recorded client entries
  """

  def __init__(self):
    # A dictionary of current attributes pertaining to the host.
    self.attrs = {}

    # A list of pairs consisting of a timestamp and a dictionary of recorded
    # attributes.
    self.log = []

  def __repr__(self):
    return 'attrs=%s, log=%s' % (self.attrs, self.log)

  def AddLogEntry(self, entry):
    """Append a new log entry."""
    # Append a timestamp.
    assert not 'timestamp' in entry, 'Oops, timestamp field already in use'
    entry['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')
    # Add entry to hosts' message log.
    self.log.append(entry)


class HostInfoTable(object):
  """Records information about a set of hosts who engage in update activity.

  Attributes:
    table: Table of information on hosts.
  """

  def __init__(self):
    # A dictionary of host information. Keys are normally IP addresses.
    self.table = {}

  def __repr__(self):
    return '%s' % self.table

  def GetInitHostInfo(self, host_id):
    """Return a host's info object, or create a new one if none exists."""
    return self.table.setdefault(host_id, HostInfo())

  def GetHostInfo(self, host_id):
    """Return an info object for given host, if such exists."""
    return self.table.get(host_id)


class Autoupdate(build_util.BuildObject):
  """Class that contains functionality that handles Chrome OS update pings."""

  _PAYLOAD_URL_PREFIX = '/static/'

  def __init__(self, xbuddy, payload_path=None, proxy_port=None,
               critical_update=False, max_updates=-1, host_log=False,
               *args, **kwargs):
    """Initializes the class.

    Args:
      xbuddy: The xbuddy path.
      payload_path: The path to pre-generated payload to serve.
      proxy_port: The port of local proxy to tell client to connect to you
        through.
      critical_update: Whether provisioned payload is critical.
      max_updates: The maximum number of updates we'll try to provision.
      host_log: Record full history of host update events.
    """
    super(Autoupdate, self).__init__(*args, **kwargs)
    self.xbuddy = xbuddy
    self.payload_path = payload_path
    self.proxy_port = proxy_port
    self.critical_update = critical_update
    self.max_updates = max_updates
    self.host_log = host_log

    # Initialize empty host info cache. Used to keep track of various bits of
    # information about a given host.  A host is identified by its IP address.
    # The info stored for each host includes a complete log of events for this
    # host, as well as a dictionary of current attributes derived from events.
    self.host_infos = HostInfoTable()

    self._update_count_lock = threading.Lock()

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

  def _LogRequest(self, request):
    """Logs the incoming request in the hostlog.

    Args:
      request: A nebraska.Request object representing the update request.

    Returns:
      A named tuple containing attributes of the update requests as the
      following fields: 'board', 'event_result' and 'event_type'.
    """
    if not self.host_log:
      return

    # Add attributes to log message. Some of these values might be None.
    log_message = {
        'version': request.version,
        'track': request.track,
        'board': request.board or self.GetDefaultBoardID(),
        'event_result': request.app_requests[0].event_result,
        'event_type': request.app_requests[0].event_type,
        'previous_version': request.app_requests[0].previous_version,
    }
    if log_message['previous_version'] is None:
      del log_message['previous_version']

    # Determine request IP, strip any IPv6 data for simplicity.
    client_ip = cherrypy.request.remote.ip.split(':')[-1]
    # Obtain (or init) info object for this client.
    curr_host_info = self.host_infos.GetInitHostInfo(client_ip)
    curr_host_info.AddLogEntry(log_message)

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
    path_to_payload = None
    # TODO(crbug.com/1006305): deprecate --payload flag
    if self.payload_path:
      # Copy the image from the path to '/forced_payload'
      label = 'forced_payload'
      dest_path = os.path.join(self.static_dir, label, constants.UPDATE_FILE)
      dest_stateful = os.path.join(self.static_dir, label,
                                   constants.STATEFUL_FILE)
      dest_meta = os.path.join(self.static_dir, label,
                               constants.UPDATE_METADATA_FILE)

      src_path = os.path.abspath(self.payload_path)
      src_meta = os.path.abspath(self.payload_path + '.json')
      src_stateful = os.path.join(os.path.dirname(src_path),
                                  constants.STATEFUL_FILE)
      common_util.MkDirP(os.path.join(self.static_dir, label))
      common_util.SymlinkFile(src_path, dest_path)
      common_util.SymlinkFile(src_meta, dest_meta)
      if os.path.exists(src_stateful):
        # The stateful payload is optional.
        common_util.SymlinkFile(src_stateful, dest_stateful)
      else:
        _Log('WARN: %s not found. Expected for dev and test builds',
             constants.STATEFUL_FILE)
        if os.path.exists(dest_stateful):
          os.remove(dest_stateful)
      path_to_payload = self.GetUpdateForLabel(label)
    else:
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

  def HandleUpdatePing(self, data, label=''):
    """Handles an update ping from an update client.

    Args:
      data: XML blob from client.
      label: optional label for the update.

    Returns:
      Update payload message for client.
    """
    # Get the static url base that will form that base of our update url e.g.
    # http://hostname:8080/static/update.gz.
    static_urlbase = self.GetStaticUrl()

    # Process attributes of the update check.
    request = nebraska.Request(data)
    self._LogRequest(request)

    if request.request_type == nebraska.Request.RequestType.EVENT:
      if (request.app_requests[0].event_type ==
          nebraska.Request.EVENT_TYPE_UPDATE_DOWNLOAD_STARTED and
          request.app_requests[0].event_result ==
          nebraska.Request.EVENT_RESULT_SUCCESS):
        with self._update_count_lock:
          if self.max_updates == 0:
            _Log('Received too many download_started notifications. This '
                 'probably means a bug in the test environment, such as too '
                 'many clients running concurrently. Alternatively, it could '
                 'be a bug in the update client.')
          elif self.max_updates > 0:
            self.max_updates -= 1

      _Log('A non-update event notification received. Returning an ack.')
      nebraska_obj = nebraska.Nebraska()
      return nebraska_obj.GetResponseToRequest(request)

    # Make sure that we did not already exceed the max number of allowed update
    # responses. Note that the counter is only decremented when the client
    # reports an actual download, to avoid race conditions between concurrent
    # update requests from the same client due to a timeout.
    if self.max_updates == 0:
      _Log('Request received but max number of updates already served.')
      nebraska_obj = nebraska.Nebraska()
      return nebraska_obj.GetResponseToRequest(request, no_update=True)

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
    nebraska_obj = nebraska.Nebraska(update_payloads_address=base_url,
                                     update_metadata_dir=local_payload_dir)
    return nebraska_obj.GetResponseToRequest(
        request, critical_update=self.critical_update)

  def HandleHostInfoPing(self, ip):
    """Returns host info dictionary for the given IP in JSON format."""
    assert ip, 'No ip provided.'
    if ip in self.host_infos.table:
      return json.dumps(self.host_infos.GetHostInfo(ip).attrs)

  def HandleHostLogPing(self, ip):
    """Returns a complete log of events for host in JSON format."""
    # If all events requested, return a dictionary of logs keyed by IP address.
    if ip == 'all':
      return json.dumps(
          dict([(key, self.host_infos.table[key].log)
                for key in self.host_infos.table]))

    # Otherwise we're looking for a specific IP address, so find its log.
    if ip in self.host_infos.table:
      return json.dumps(self.host_infos.GetHostInfo(ip).log)

    # If no events were logged for this IP, return an empty log.
    return json.dumps([])
