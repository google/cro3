#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright 2018 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Mock Omaha server"""

from __future__ import print_function

# pylint: disable=cros-logging-import
import argparse
import base64
import copy
import json
import logging
import os
import signal
import sys
import threading
import traceback
import urlparse

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, time
from xml.dom import minidom
from xml.etree import ElementTree


class NebraskaError(Exception):
  """The base class for failures raised by Nebraska."""


class NebraskaErrorInvalidRequest(NebraskaError):
  """Raised for invalid requests."""


class Request(object):
  """Request consisting of a list of apps to update/install."""

  APP_TAG = 'app'
  APP_APPID_ATTR = 'appid'
  APP_DELTA_OKAY_ATTR = 'delta_okay'
  # The following app attributes should be the same for all incoming apps if
  # they exist. 'version' should be repeated in all apps, but other attributes
  # can be omited in non-platform apps. Or at least they should be present in
  # one of the apps. For this reason we keep these values in the Request
  # object itself and not the AppRequest (except for 'version').
  APP_VERSION_ATTR = 'version'
  APP_HW_CLASS_ATTR = 'hardware_class'
  APP_CHANNEL_ATTR = 'track'
  APP_BOARD_ATTR = 'board'

  UPDATE_CHECK_TAG = 'updatecheck'

  PING_TAG = 'ping'

  EVENT_TAG = 'event'
  EVENT_TYPE_ATTR = 'eventtype'
  EVENT_RESULT_ATTR = 'eventresult'
  EVENT_PREVIOUS_VERSION_ATTR = 'previousversion'

  # Update events and result codes.
  EVENT_TYPE_UNKNOWN = 0
  EVENT_TYPE_DOWNLOAD_COMPLETE = 1
  EVENT_TYPE_INSTALL_COMPLETE = 2
  EVENT_TYPE_UPDATE_COMPLETE = 3
  EVENT_TYPE_UPDATE_DOWNLOAD_STARTED = 13
  EVENT_TYPE_UPDATE_DOWNLOAD_FINISHED = 14

  EVENT_RESULT_ERROR = 0
  EVENT_RESULT_SUCCESS = 1
  EVENT_RESULT_SUCCESS_REBOOT = 2
  EVENT_RESULT_UPDATE_DEFERRED = 9

  class RequestType(object):
    """Simple enumeration for encoding request type."""
    INSTALL = 1 # Request installation of a new app.
    UPDATE = 2 # Request update for an existing app.
    EVENT = 3 # Just an event request.

  def __init__(self, request_str):
    """Initializes a request instance.

    Args:
      request_str: XML-formatted request string.
    """
    self.request_str = request_str

    self.version = None
    self.hardware_class = None
    self.track = None
    self.board = None
    self.request_type = None

    self.app_requests = []

    self.ParseRequest()

  def ParseRequest(self):
    """Parse an XML request string into a list of app requests.

    An app request can be a no-op, an install request, or an update request, and
    may include a ping and/or event tag. We treat app requests with the update
    tag omitted as no-ops, since the server is not required to return payload
    information. Install requests are signalled by sending app requests along
    with a no-op request for the platform app.

    Returns:
      A list of AppRequest instances.

    Raises:
      NebrakaErrorInvalidRequest if the request string is not a valid XML
          request.
    """
    try:
      request_root = ElementTree.fromstring(self.request_str)
    except ElementTree.ParseError as err:
      raise NebraskaErrorInvalidRequest(
          'Request string is not valid XML: {}'.format(err))

    # TODO(http://crbug.com/914936): It would be better to specifically check
    # the platform app. An install is signalled by omitting the update_check for
    # the platform app, so we assume that if we have one appid for which the
    # update_check tag is omitted, it is the platform app and this is an install
    # request. This assumption should be fine since we never mix updates with
    # requests that do not include an update_check tag.
    app_elements = request_root.findall(self.APP_TAG)
    update_check_count = len(
        [x for x in app_elements if x.find(self.UPDATE_CHECK_TAG) is not None])
    if update_check_count == 0:
      self.request_type = Request.RequestType.EVENT
    elif update_check_count == len(app_elements) - 1:
      self.request_type = Request.RequestType.INSTALL
    elif update_check_count == len(app_elements):
      self.request_type = Request.RequestType.UPDATE
    else:
      raise NebraskaErrorInvalidRequest(
          'Client request omits update_check tag for more than one, but not all'
          ' app requests.')

    for app in app_elements:
      app_request = Request.AppRequest(app, self.request_type)
      self.app_requests.append(app_request)

    def _CheckAttributesAndReturnIt(attribute, in_all=False):
      """Checks the attribute integrity among all apps and return its value.

      The assumption is that the value of the attribute is the same for all apps
      if existed. It can optionally be in one or more apps, but they are all
      equal.

      Args:
        attribute: An attribute of the app tag.
        in_all: If true, the attribute should exist among all apps.

      Returns:
        The value of the attribute (which is same among all app tags).
      """
      all_attrs = [getattr(x, attribute) for x in self.app_requests]
      if in_all and None in all_attrs:
        raise NebraskaErrorInvalidRequest(
            'All apps should have "{}" attribute.'.format(attribute))

      # Filter out the None elements into a set.
      unique_attrs = set(filter(None, all_attrs))
      if len(unique_attrs) == 0:
        raise NebraskaErrorInvalidRequest('"{}" attribute should appear in at '
                                          'least one app.'.format(attribute))
      if len(unique_attrs) > 1:
        raise NebraskaErrorInvalidRequest(
            'Attribute "{}" is not the same in all app tags.'.format(attribute))
      return unique_attrs.pop()

    self.version = _CheckAttributesAndReturnIt(self.APP_VERSION_ATTR,
                                               in_all=True)
    self.hardware_class = _CheckAttributesAndReturnIt(self.APP_HW_CLASS_ATTR)
    self.track = _CheckAttributesAndReturnIt(self.APP_CHANNEL_ATTR)
    self.board = _CheckAttributesAndReturnIt(self.APP_BOARD_ATTR)


  class AppRequest(object):
    """An app request.

    Can be an update request, install request, or neither if the update check
    tag is omitted (i.e. the platform app when installing a DLC, or when a
    request is only an event), in which case we treat the request as a no-op.
    An app request can also send pings and event result information.
    """

    def __init__(self, app, request_type):
      """Initializes a Request.

      Args:
        app: The request app XML element.
        request_type: install, update, or event.

        More on event pings:
        https://github.com/google/omaha/blob/master/doc/ServerProtocolV3.md
      """
      self.request_type = request_type
      self.appid = None
      self.version = None
      self.hardware_class = None
      self.track = None
      self.board = None
      self.ping = None
      self.delta_okay = None
      self.event_type = None
      self.event_result = None
      self.previous_version = None

      self.ParseApp(app)

    def __str__(self):
      """Returns a string representation of an AppRequest."""
      if self.request_type == Request.RequestType.EVENT:
        return '{}'.format(self.appid)
      elif self.request_type == Request.RequestType.INSTALL:
        return 'install {} v{}'.format(self.appid, self.version)
      elif self.request_type == Request.RequestType.UPDATE:
        return '{} update {} from v{}'.format(
            'delta' if self.delta_okay else 'full', self.appid, self.version)

    def ParseApp(self, app):
      """Parses the app XML element and populates the self object.

      Args:
        app: The request app XML element.

      Raises NebraskaErrorInvalidRequest if the input request string is in
          invalid format.
      """
      self.appid = app.get(Request.APP_APPID_ATTR)
      self.version = app.get(Request.APP_VERSION_ATTR)
      self.hardware_class = app.get(Request.APP_HW_CLASS_ATTR)
      self.track = app.get(Request.APP_CHANNEL_ATTR)
      self.board = app.get(Request.APP_BOARD_ATTR)
      self.delta_okay = app.get(Request.APP_DELTA_OKAY_ATTR) == 'true'

      event = app.find(Request.EVENT_TAG)
      if event is not None:
        self.event_type = event.get(Request.EVENT_TYPE_ATTR)
        self.event_result = event.get(Request.EVENT_RESULT_ATTR, 0)
        self.previous_version = event.get(Request.EVENT_PREVIOUS_VERSION_ATTR)

      self.ping = app.find(Request.PING_TAG) is not None

      if None in (self.request_type, self.appid, self.version):
        raise NebraskaErrorInvalidRequest('Invalid app request.')

    def MatchAppData(self, app_data, partial_match_appid=False):
      """Returns true iff the app matches a given client request.

      An app matches a request if the appid matches the requested appid.
      Additionally, if the app describes a delta update payload, the request
      must be able to accept delta payloads.

      Args:
        app_data: An AppData object describing a valid app data.
        partial_match_appid: If true, it will partially check the app_data's
            appid.  Which means that if app_data's appid is a substring of
            request's appid, it will be a match.

      Returns:
        True if the request matches the given app, False otherwise.
      """
      if self.appid != app_data.appid:
        if not partial_match_appid or (app_data.appid is not None and
                                       app_data.appid not in self.appid):
          return False

      if self.request_type == Request.RequestType.UPDATE:
        if app_data.is_delta:
          return self.delta_okay
        else:
          return True

      if self.request_type == Request.RequestType.INSTALL:
        return not app_data.is_delta

      return False


class Response(object):
  """An update/install response.

  A response to an update or install request consists of an XML-encoded list
  of responses for each appid in the client request. This class takes a list of
  responses for update/install requests and compiles them into a single element
  constituting an aggregate response that can be returned to the client in XML
  format based on the format of an XML response template.
  """

  def __init__(self, request, properties):
    """Initialize a reponse from a list of matching apps.

    Args:
      request: Request instance describing client requests.
      properties: An instance of NebraskaProperties.
    """
    self._request = request
    self._properties = properties

    curr = datetime.now()
    self._elapsed_days = (curr - datetime(2007, 1, 1)).days
    self._elapsed_seconds = int((
        curr - datetime.combine(curr.date(), time.min)).total_seconds())

  def GetXMLString(self):
    """Generates a response to a set of client requests.

    Given a client request consisting of one or more app requests, generate a
    response to each of these requests and combine them into a single
    XML-formatted response.

    Returns:
      XML-formatted response string consisting of a response to each app request
      in the incoming request from the client.
    """
    try:
      response_xml = ElementTree.Element(
          'response', attrib={'protocol': '3.0', 'server': 'nebraska'})
      ElementTree.SubElement(
          response_xml, 'daystart',
          attrib={'elapsed_days': str(self._elapsed_days),
                  'elapsed_seconds': str(self._elapsed_seconds)})

      for app_request in self._request.app_requests:
        logging.debug('Request for appid %s', str(app_request))
        response_xml.append(
            self.AppResponse(app_request, self._properties).Compile())

    except Exception as err:
      logging.error(traceback.format_exc())
      raise NebraskaError('Failed to compile response: {}'.format(err))

    return ElementTree.tostring(
        response_xml, encoding='UTF-8', method='xml')

  class AppResponse(object):
    """Response to an app request.

    If the request was an update or install request, the response should include
    a matching app if one was found. Addionally, the response should include
    responses to pings and events as appropriate.
    """

    def __init__(self, app_request, properties):
      """Initialize an AppResponse.

      Attributes:
        app_request: AppRequest representing a client request.
        properties: An instance of NebraskaProperties.
      """
      self._app_request = app_request
      self._app_data = None
      self._err_not_found = False
      self._payloads_address = None
      self._critical_update = False

      # If no update was requested, don't process anything anymore.
      if properties.no_update:
        return

      if self._app_request.request_type == Request.RequestType.INSTALL:
        self._app_data = properties.install_app_index.Find(self._app_request)
        self._err_not_found = self._app_data is None
        self._payloads_address = properties.install_payloads_address
      elif self._app_request.request_type == Request.RequestType.UPDATE:
        self._app_data = properties.update_app_index.Find(self._app_request)
        self._payloads_address = properties.update_payloads_address
        # This differentiates between apps that are not in the index and apps
        # that are available, but do not have an update available. Omaha treats
        # the former as an error, whereas the latter case should result in a
        # response containing a "noupdate" tag.
        self._err_not_found = (self._app_data is None and
                               not properties.update_app_index.Contains(
                                   self._app_request))
        self._critical_update = properties.critical_update

      if self._app_data:
        logging.debug('Found matching payload: %s', str(self._app_data))
      elif self._err_not_found:
        logging.debug('No matches for appid %s', self._app_request.appid)
      elif self._app_request.request_type == Request.RequestType.UPDATE:
        logging.debug('No updates available for %s', self._app_request.appid)

    def Compile(self):
      """Compiles an app description into XML format.

      Compile the app description into an ElementTree Element that can be used
      to compile a response to a client request, and ultimately converted into
      XML.

      Returns:
        An ElementTree Element instance describing an update or install payload.
      """
      app_response = ElementTree.Element(
          'app', attrib={'appid': self._app_request.appid, 'status': 'ok'})

      if self._app_request.ping:
        ElementTree.SubElement(app_response, 'ping', attrib={'status': 'ok'})
      if self._app_request.event_type is not None:
        ElementTree.SubElement(app_response, 'event', attrib={'status': 'ok'})

      if self._app_data is not None:
        update_check = ElementTree.SubElement(
            app_response, 'updatecheck', attrib={'status': 'ok'})
        urls = ElementTree.SubElement(update_check, 'urls')
        ElementTree.SubElement(
            urls, 'url', attrib={'codebase': self._payloads_address})
        manifest = ElementTree.SubElement(
            update_check, 'manifest',
            attrib={'version': self._app_data.target_version})
        actions = ElementTree.SubElement(manifest, 'actions')
        ElementTree.SubElement(
            actions, 'action',
            attrib={'event': 'update', 'run': self._app_data.name})
        action = ElementTree.SubElement(
            actions, 'action',
            attrib={'ChromeOSVersion': self._app_data.target_version,
                    'ChromeVersion': '1.0.0.0',
                    'IsDeltaPayload': str(self._app_data.is_delta).lower(),
                    'MaxDaysToScatter': '14',
                    'MetadataSignatureRsa': self._app_data.metadata_signature,
                    'MetadataSize': str(self._app_data.metadata_size),
                    'event': 'postinstall'})
        if self._critical_update:
          action.set('deadline', 'now')
        if self._app_data.public_key is not None:
          action.set('PublicKeyRsa', self._app_data.public_key)
        packages = ElementTree.SubElement(manifest, 'packages')
        ElementTree.SubElement(
            packages, 'package',
            attrib={'fp': '1.%s' % self._app_data.sha256_hex,
                    'hash_sha256': self._app_data.sha256_hex,
                    'name': self._app_data.name,
                    'required': 'true',
                    'size': str(self._app_data.size)})

      elif self._err_not_found:
        app_response.set('status', 'error-unknownApplication')

      elif self._app_request.request_type == Request.RequestType.UPDATE:
        ElementTree.SubElement(app_response, 'updatecheck',
                               attrib={'status': 'noupdate'})

      return app_response


class AppIndex(object):
  """An index of available app payload information.

  Index of available apps used to generate responses to Omaha requests. The
  index consists of lists of payload information associated with a given appid,
  since we can have multiple payloads for a given app (delta/full payloads). The
  index is built by scanning a given directory for json files that describe the
  available payloads.
  """

  def __init__(self, directory):
    """Initializes an AppIndex instance.

    Attributes:
      directory: Directory containing metdata and payloads, can be None.
      index: A list of AppData describing payloads.
    """
    self._directory = directory
    self._index = []

  def Scan(self):
    """Scans the directory and loads all available properties files."""
    if self._directory is None:
      return

    for f in os.listdir(self._directory):
      if f.endswith('.json'):
        try:
          with open(os.path.join(self._directory, f), 'r') as metafile:
            metadata_str = metafile.read()
            metadata = json.loads(metadata_str)
            # Get the name from file name itself, assuming the metadata file
            # ends with '.json'.
            metadata[AppIndex.AppData.NAME_KEY] = f[:-len('.json')]
            app = AppIndex.AppData(metadata)
            self._index.append(app)
        except (IOError, KeyError, ValueError) as err:
          logging.error('Failed to read app data from %s (%s)', f, str(err))
          raise
        logging.debug('Found app data: %s', str(app))

  def Find(self, request):
    """Search the index for a given appid.

    Searches the index for the payloads matching a client request. Matching is
    based on appid, and whether the client is searching for an update and can
    handle delta payloads.

    Args:
      request: AppRequest describing the client request.

    Returns:
      An AppData object describing an available payload matching the client
      request, or None if no matches are found. Prefer delta payloads if the
      client can accept them and if one is available.
    """
    # Find a list of payloads exactly matching the client request.
    matches = [app_data for app_data in self._index if
               request.MatchAppData(app_data)]

    if not matches:
      # Look to see if there is any AppData with empty or partial App ID. Then
      # return the first one you find. This basically will work as a wild card
      # to allow AppDatas that don't have an AppID or their AppID is incomplete
      # (e.g. empty platform App ID + _ + DLC App ID) to work just fine.
      #
      # The reason we just don't do this in one pass is that we want to find all
      # the matches with exact appid and iif there was no match, we do the appid
      # partial match.
      matches = [app_data for app_data in self._index if
                 request.MatchAppData(app_data, partial_match_appid=True)]

    if not matches:
      return None

    # If the client can handle a delta, prefer to send a delta.
    if request.delta_okay:
      match = next((x for x in matches if x.is_delta), None)
      match = match if match else next(iter(matches), None)
    else:
      match = next(iter(matches), None)

    return copy.copy(match)

  def Contains(self, request):
    """Checks if the AppIndex contains any apps matching a given request appid.

    Checks the index for an appid (partially) matching the appid in the given
    request. This is necessary because it allows us to differentiate between the
    case where we have no new versions of an app and the case where we have no
    information about an app at all.

    Args:
      request: Describes the client request.

    Returns:
      True if the index contains any appids matching the appid given in the
      request.
    """
    return any(app_data.appid in request.appid for app_data in self._index)

  class AppData(object):
    """Data about an available app.

    Data about an available app that can be either installed or upgraded
    to. This information is compiled into XML format and returned to the client
    in an app tag in the server's response to an update or install request.
    """

    APPID_KEY = 'appid'
    NAME_KEY = 'name'
    IS_DELTA_KEY = 'is_delta'
    SIZE_KEY = 'size'
    METADATA_SIG_KEY = 'metadata_signature'
    METADATA_SIZE_KEY = 'metadata_size'
    TARGET_VERSION_KEY = 'target_version'
    SOURCE_VERSION_KEY = 'source_version'
    SHA256_HEX_KEY = 'sha256_hex'
    PUBLIC_KEY_RSA_KEY = 'public_key'

    def __init__(self, app_data):
      """Initialize AppData.

      Args:
        app_data: Dictionary containing attributes used to initialize AppData
            instance.

      Attributes:
        template: Defines the format of an app element in the XML response.
        appid: appid of the requested app.
        name: Filename of requested app on the mock Lorry server.
        is_delta: True iff the payload is a delta update.
        size: Size of the payload.
        metadata_signature: Metadata signature.
        metadata_size: Metadata size.
        sha256_hex: SHA256 hash of the payload encoded in hexadecimal.
        target_version: ChromeOS version the payload is tied to.
        source_version: Source version for delta updates.
        public_key: The public key for signature verification. It should be in
            base64 format.
      """
      self.appid = app_data[self.APPID_KEY]
      self.name = app_data[self.NAME_KEY]
      self.target_version = app_data[self.TARGET_VERSION_KEY]
      self.is_delta = app_data[self.IS_DELTA_KEY]
      self.source_version = (
          app_data[self.SOURCE_VERSION_KEY] if self.is_delta else None)
      self.size = app_data[self.SIZE_KEY]
      # Sometimes the payload is not signed, hence the matadata signature is
      # null, but we should pass empty string instead of letting the value be
      # null (the XML element tree will break).
      self.metadata_signature = app_data[self.METADATA_SIG_KEY] or ''
      self.metadata_size = app_data[self.METADATA_SIZE_KEY]
      self.public_key = app_data.get(self.PUBLIC_KEY_RSA_KEY)
      # Unfortunately the sha256_hex that paygen generates is actually a base64
      # sha256 hash of the payload for some unknown historical reason. But the
      # Omaha response contains the hex value of that hash. So here convert the
      # value from base64 to hex so nebraska can send the correct version to the
      # client. See b/131762584.
      self.sha256_hex = base64.b64decode(
          app_data[self.SHA256_HEX_KEY]).encode('hex')
      self.url = None # Determined per-request.

    def __str__(self):
      if self.is_delta:
        return '{} v{}: delta update from base v{}'.format(
            self.appid, self.target_version, self.source_version)
      return '{} v{}: full update/install'.format(
          self.appid, self.target_version)


class NebraskaProperties(object):
  """An instance of this class contains some Nebraska properties."""

  def __init__(self, update_payloads_address, install_payloads_address,
               update_app_index, install_app_index):
    """Initializes the NebraskaProperties instance.

    Args:
      update_payloads_address: Address serving update payloads.
      install_payloads_address: Address serving install payloads.
      update_app_index: Index of update payloads.
      install_app_index: Index of install payloads.
    """
    self.update_payloads_address = update_payloads_address
    self.install_payloads_address = install_payloads_address
    self.update_app_index = update_app_index
    self.install_app_index = install_app_index
    self.critical_update = False
    self.no_update = False


class Nebraska(object):
  """An instance of this class allows responding to incoming Omaha requests.

    This class has the responsibility to manufacture Omaha responses based on
    the input update requests. This should be the main point of use of the
    Nebraska. If any changes to the behavior of Nebraska is intended, like
    creating critical update responses, or messing up with firmware and kernel
    versions, new flags should be added here to add that feature.
  """

  def __init__(self,
               update_payloads_address=None,
               install_payloads_address=None,
               update_metadata_dir=None,
               install_metadata_dir=None):
    """Initializes the Nebraska instance.

    Args:
      update_payloads_address: Address of the update payload server.
      install_payloads_address: Address of the install payload server. If None
           is passed it will default to update_payloads_address.
      update_metadata_dir: Update payloads metadata directory.
      install_metadata_dir: Install payloads metadata directory.
    """
    # Attach '/' at the end of the addresses if they don't have any. The update
    # engine just concatenates the base address with the payload file name and
    # if there is no '/' the path will be invalid.
    upa = os.path.join(update_payloads_address or '', '')
    ipa = (os.path.join(install_payloads_address, '')
           if install_payloads_address is not None else upa)
    uai = AppIndex(update_metadata_dir)
    iai = AppIndex(install_metadata_dir)
    uai.Scan()
    iai.Scan()

    self._properties = NebraskaProperties(upa, ipa, uai, iai)

  def GetResponseToRequest(self, request, critical_update=False,
                           no_update=False):
    """Returns the response corresponding to a request.

    Args:
      request: The Request object representation of the incoming request.
      critical_update: If true, the response will include 'deadline=now' which
          indicates the update is critical.
      no_update: If true, it will return a noupdate response regardless.

    Returns:
      The string representation of the created response.
    """
    properties = copy.copy(self._properties)
    properties.critical_update = critical_update
    properties.no_update = no_update
    response = Response(request, properties).GetXMLString()
    # Make the XML response look pretty.
    return minidom.parseString(response).toprettyxml(indent='  ',
                                                     encoding='UTF-8')


class NebraskaServer(object):
  """A simple Omaha server instance.

  A simple mock of an Omaha server. Responds to XML-formatted update/install
  requests based on the contents of metadata files in update and install
  directories, respectively. These metadata files are used to configure
  responses to Omaha requests from Update Engine and describe update and install
  payloads provided by another server.
  """

  def __init__(self, nebraska, port=0):
    """Initializes a server instance.

    Args:
      nebraska: The Nebraska instance to process requests and responses.
      port: Port the server should run on, 0 if the OS should assign a port.
    """
    self._port = port
    self._httpd = None
    self._server_thread = None
    self.nebraska = nebraska

  class NebraskaHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Omaha requests."""

    def do_POST(self):
      """Responds to XML-formatted Omaha requests.

      The URL path can be like:
        - https://<ip>:<port>/?critical_update=true # For requesting a critical
          update response
      """
      request_len = int(self.headers.getheader('content-length'))
      request = self.rfile.read(request_len)
      logging.debug('Received request: %s', request)

      parsed_query = urlparse.parse_qs(urlparse.urlparse(self.path).query)
      critical_update = parsed_query.get('critical_update', []) == ['true']

      try:
        request_obj = Request(request)
        response = self.server.owner.nebraska.GetResponseToRequest(
            request_obj, critical_update=critical_update)
      except Exception as err:
        logging.error('Failed to handle request (%s)', str(err))
        logging.error(traceback.format_exc())
        self.send_error(500, 'Failed to handle incoming request')
        return

      self.send_response(200)
      self.send_header('Content-Type', 'application/xml')
      self.end_headers()
      self.wfile.write(response)

  def Start(self):
    """Starts a mock Omaha HTTP server."""
    self._httpd = HTTPServer(('', self.GetPort()),
                             NebraskaServer.NebraskaHandler)
    self._port = self._httpd.server_port
    self._httpd.owner = self
    self._server_thread = threading.Thread(target=self._httpd.serve_forever)
    self._server_thread.start()

  def Stop(self):
    """Stops the mock Omaha server."""
    self._httpd.shutdown()
    self._server_thread.join()

  def GetPort(self):
    """Returns the server's port."""
    return self._port


def ParseArguments(argv):
  """Parses command line arguments.

  Args:
    argv: List of commandline arguments.

  Returns:
    Namespace object containing parsed arguments.
  """
  parser = argparse.ArgumentParser(description=__doc__)

  parser.add_argument('--update-metadata', metavar='DIR', default=None,
                      help='Payloads metadata directory for update.')
  parser.add_argument('--install-metadata', metavar='DIR', default=None,
                      help='Payloads metadata directory for install.')
  parser.add_argument('--update-payloads-address', metavar='URL',
                      help='Base payload URI for update payloads',
                      default='http://127.0.0.1:8080')
  parser.add_argument('--install-payloads-address', metavar='URL',
                      help='Base payload URI for install payloads. If not '
                      'passed it will default to --update-payloads-address')

  parser.add_argument('--port', metavar='PORT', type=int, default=0,
                      help='Port to run the server on.')
  parser.add_argument('--runtime-root', metavar='DIR',
                      default='/run/nebraska',
                      help='The root directory in which nebraska will write its'
                      ' pid and port files.')
  parser.add_argument('--log-file', metavar='FILE',
                      help='The file to write the logs.')

  return parser.parse_args(argv[1:])


def main(argv):
  """Main function."""
  opts = ParseArguments(argv)

  # Reset the log file.
  if opts.log_file:
    with open(opts.log_file, 'w') as _:
      pass

  logging.basicConfig(filename=opts.log_file if opts.log_file else None,
                      level=logging.DEBUG)

  logging.info('Starting nebraska ...')

  nebraska = Nebraska(
      update_payloads_address=opts.update_payloads_address,
      install_payloads_address=opts.install_payloads_address,
      update_metadata_dir=opts.update_metadata,
      install_metadata_dir=opts.install_metadata)
  nebraska_server = NebraskaServer(nebraska, port=opts.port)

  def handler(signum, _):
    logging.info('Exiting Nebraska with signal %d ...', signum)
    nebraska_server.Stop()

  signal.signal(signal.SIGINT, handler)
  signal.signal(signal.SIGTERM, handler)

  nebraska_server.Start()

  if not os.path.exists(opts.runtime_root):
    os.makedirs(opts.runtime_root)

  runtime_files = {
      os.path.join(opts.runtime_root, 'port'): str(nebraska_server.GetPort()),
      os.path.join(opts.runtime_root, 'pid'): str(os.getpid()),
  }

  for k, v in runtime_files.items():
    with open(k, 'w') as f:
      f.write(v)

  logging.info('Started nebraska on port %d and pid %d.',
               nebraska_server.GetPort(), os.getpid())

  signal.pause()

  # Remove the pid and port files.
  for f in runtime_files:
    try:
      os.remove(f)
    except Exception as e:
      logging.warn('Failed to remove file %s with error %s', f, e)

  return os.EX_OK


if __name__ == '__main__':
  sys.exit(main(sys.argv))
