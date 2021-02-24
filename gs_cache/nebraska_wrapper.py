# -*- coding: utf-8 -*-
# Copyright 2020 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""A Nebraska Wrapper to handle update client requests."""

from __future__ import print_function

import os
import re
import shutil
import tempfile

import requests
from six.moves import urllib

import cherrypy  # pylint: disable=import-error

# Nebraska.py has been added to PYTHONPATH, so gs_archive_server should be able
# to import nebraska.py directly. But if gs_archive_server is triggered from
# ~/chromiumos/src/platform/dev, it will import nebraska, the python package,
# instead of nebraska.py, thus throwing an AttributeError when the module is
# eventually used. To mitigate this, catch the exception and import nebraska.py
# from the nebraska package directly.
try:
  import nebraska
  nebraska.QueryDictToDict({})
except AttributeError as e:
  from nebraska import nebraska

from chromite.lib import cros_logging as logging


# Define module logger.
_logger = logging.getLogger(__file__)

# Define all GS Cache related constants.
GS_CACHE_PORT = '8888'
GS_ARCHIVE_BUCKET = 'chromeos-image-archive'
GS_CACHE_DWLD_RPC = 'download'
GS_CACHE_LIST_DIR_RPC = 'list_dir'


def _log(*args, **kwargs):
  """A wrapper function of logging.debug/info, etc."""
  level = kwargs.pop('level', logging.DEBUG)
  _logger.log(level, extra=cherrypy.request.headers, *args, **kwargs)


class NebraskaWrapperError(Exception):
  """Exception class used by this module."""
  # pylint: disable=unnecessary-pass
  pass


class NebraskaWrapper(object):
  """Class that contains functionality that handles Chrome OS update pings."""

  # Define regexes for properties file. These patterns are the same as the ones
  # defined in chromite/lib/xbuddy/build_artifact.py. Only the '.*' in the
  # beginning and '$' at the end is different as in this class, we need to
  # compare the full gs URL of the file without a newline at the end to this
  # regex pattern.
  _FULL_PAYLOAD_PROPS_PATTERN = r'.*chromeos_.*_full_dev.*bin(\.json)$'
  _DELTA_PAYLOAD_PROPS_PATTERN = r'.*chromeos_.*_delta_dev.*bin(\.json)$'

  def __init__(self, label, server_addr, full_update):
    """Initializes the class.

    Args:
      label: Label (string) for the update, typically in the format
          <board>-<XXXX>/Rxx-xxxxx.x.x-<unique string>.
      server_addr: IP address (string) for the server on which gs cache is
          running.
      full_update: Indicates whether the requested update is full or delta. The
          string values for this argument can be 'True', 'False', or
          'unspecified'.
    """
    self._label = self._GetLabel(label)
    self._gs_cache_base_url = 'http://%s:%s' % (server_addr, GS_CACHE_PORT)

    # When full_update parameter is not specified in the request, the update
    # type is 'delta'.
    self._is_full_update = full_update.lower().strip() == 'true'

    self._props_dir = tempfile.mkdtemp(prefix='gsc-update')
    self._payload_props_file = None

  def __enter__(self):
    """Called while entering context manager; does nothing."""
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    """Called while exiting context manager; cleans up temp dirs."""
    try:
      shutil.rmtree(self._props_dir)
    except Exception as e:
      _log('Something went wrong. Could not delete %s due to exception: %s',
           self._props_dir, e, level=logging.WARNING)

  @property
  def _PayloadPropsFilename(self):
    """Get the name of the payload properties file.

    The name of the properties file is obtained from the list of files returned
    by the list_dir RPC by matching the name of the file with the update_type
    and file extension.

    Returns:
      Name of the payload properties file.

    Raises:
      NebraskaWrapperError if the list_dir calls returns 4xx/5xx or if the
          correct file could not be determined.
    """
    if self._payload_props_file:
      return self._payload_props_file

    urlbase = self._GetListDirURL()
    url = urllib.parse.urljoin(urlbase, self._label)

    resp = requests.get(url)
    try:
      resp.raise_for_status()
    except Exception as e:
      raise NebraskaWrapperError('An error occurred while trying to complete '
                                 'the request: %s' % e)

    if self._is_full_update:
      pattern = re.compile(self._FULL_PAYLOAD_PROPS_PATTERN)
    else:
      pattern = re.compile(self._DELTA_PAYLOAD_PROPS_PATTERN)

    # Iterate through all listed files to determine the correct payload
    # properties file. Since the listed files will be in the format
    # gs://<gs_bucket>/<board>/<version>/<filename>, return the filename only
    # once a match is determined.
    for fname in [x.strip() for x in resp.content.strip().split('\n')]:
      if pattern.match(fname):
        self._payload_props_file = fname.rsplit('/', 1)[-1]
        return self._payload_props_file

    raise NebraskaWrapperError(
        'Request to %s returned a %s but gs_archive_server was unable to '
        'determine the name of the properties file.' %
        (url, resp.status_code))

  def _GetLabel(self, label):
    """Gets the label for the request.

    Removes a trailing /au_nton from the label argument.

    Args:
      label: A string obtained from the request.

    Returns:
      A string in the format <board>-<XXXX>/Rxx-xxxxx.x.x-<unique string>.
    """
    # TODO(crbug.com/1102552): Remove this logic once all clients stopped
    # sending au_nton in the request.
    return label[:-len('/au_nton')] if label.endswith('/au_nton') else label

  def _GetDownloadURL(self):
    """Returns the static url base that should prefix all payload responses."""
    _log('Handling update ping as %s', self._gs_cache_base_url)
    return self._GetURL(GS_CACHE_DWLD_RPC)

  def _GetListDirURL(self):
    """Returns the static url base that should prefix all list_dir requests."""
    _log('Using base URL to list contents: %s', self._gs_cache_base_url)
    return self._GetURL(GS_CACHE_LIST_DIR_RPC)

  def _GetURL(self, rpc_name):
    """Construct gs_cache URL for the given RPC.

    Args:
      rpc_name: Name of the RPC for which the URL needs to be built.

    Returns:
      Base URL to be used.
    """
    urlbase = urllib.parse.urljoin(self._gs_cache_base_url,
                                   '%s/%s/' % (rpc_name, GS_ARCHIVE_BUCKET))
    _log('Using static url base %s', urlbase)
    return urlbase

  def _GetPayloadPropertiesDir(self, urlbase):
    """Download payload properties file from GS Archive

    Args:
      urlbase: Base url that should be used to form the download request.

    Returns:
      The path to the /tmp directory which stores the payload properties file
          that nebraska will use.

    Raises:
      NebraskaWrapperError is raised if the method is unable to
          download the file for some reason.
    """
    local_payload_dir = self._props_dir
    partial_url = urllib.parse.urljoin(urlbase, '%s/' % self._label)
    _log('Downloading %s from bucket %s.', self._PayloadPropsFilename,
         partial_url, level=logging.INFO)

    try:
      resp = requests.get(urllib.parse.urljoin(partial_url,
                                               self._PayloadPropsFilename))
      resp.raise_for_status()
      file_path = os.path.join(local_payload_dir, self._PayloadPropsFilename)
      # We are not worried about multiple threads writing to the same file as
      # we are creating a different directory for each initialization of this
      # class anyway.
      with open(file_path, 'w') as f:
        f.write(resp.content)
    except Exception as e:
      raise NebraskaWrapperError('An error occurred while trying to complete '
                                 'the request: %s' % e)
    _log('Path to downloaded payload properties file: %s' % file_path)
    return local_payload_dir

  def HandleUpdatePing(self, data, **kwargs):
    """Handles an update ping from an update client.

    Args:
      data: XML blob from client.
      kwargs: The map of query strings passed to the /update API.

    Returns:
      Update payload message for client.
    """
    # Get the static url base that will form that base of our update url e.g.
    # http://<GS_CACHE_IP>:<GS_CACHE_PORT>/download/chromeos-image-archive/.
    urlbase = self._GetDownloadURL()
    # Change the URL's string query dictionary provided by cherrypy to a
    # valid dictionary that has proper values for its keys. e.g. True
    # instead of 'True'.
    kwargs = nebraska.QueryDictToDict(kwargs)

    try:
      # Process attributes of the update check.
      request = nebraska.Request(data)
      if request.request_type == nebraska.Request.RequestType.EVENT:
        _log('A non-update event notification received. Returning an ack.',
             level=logging.INFO)
        n = nebraska.Nebraska()
        n.UpdateConfig(**kwargs)
        return n.GetResponseToRequest(request)

      _log('Update Check Received.')

      base_url = urllib.parse.urljoin(urlbase, '%s/' % self._label)
      _log('Responding to client to use url %s to get image', base_url,
           level=logging.INFO)

      local_payload_dir = self._GetPayloadPropertiesDir(urlbase=urlbase)
      _log('Using %s as the update_metadata_dir for NebraskaProperties.',
           local_payload_dir)

      n = nebraska.Nebraska()
      n.UpdateConfig(update_payloads_address=base_url,
                     update_app_index=nebraska.AppIndex(local_payload_dir))
      return n.GetResponseToRequest(request)

    except Exception as e:
      raise NebraskaWrapperError('An error occurred while processing the '
                                 'update request: %s' % e)
