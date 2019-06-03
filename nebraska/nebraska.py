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

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, time
from xml.etree import ElementTree


class NebraskaError(Exception):
  """The base class for failures raised by Nebraska."""


class NebraskaErrorInvalidRequest(NebraskaError):
  """Raised for invalid requests."""


class Request(object):
  """Request consisting of a list of apps to update/install."""

  APP_TAG = 'app'
  APPID_ATTR = 'appid'
  VERSION_ATTR = 'version'
  DELTA_OKAY_ATTR = 'delta_okay'
  HW_CLASS_ATTR = 'hardware_class'
  UPDATE_CHECK_TAG = 'updatecheck'
  PING_TAG = 'ping'
  EVENT_TAG = 'event'
  EVENT_TYPE_ATTR = 'eventtype'
  EVENT_RESULT_ATTR = 'eventresult'

  def __init__(self, request_str):
    """Initializes a request instance.

    Args:
      request_str: XML-formatted request string.
    """
    self.request_str = request_str

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
          'Request string is not valid XML: {}'.format(str(err)))

    # TODO(http://crbug.com/914936): It would be better to specifically check
    # the platform app. An install is signalled by omitting the update check
    # for the platform app, which can be found based on the presense of a
    # hardware_class tag, which is absent for DLC appids. UE does not currently
    # omit hardware_class for DLCs, so we assume that if we have one appid for
    # which the update_check tag is omitted, it is the platform app and this is
    # an install request. This assumption should be fine since we never mix
    # updates with requests that do not include an update_check tag.
    app_elements = request_root.findall(self.APP_TAG)
    noop_count = len(
        [x for x in app_elements if x.find(self.UPDATE_CHECK_TAG) is None])

    if noop_count > 1 and noop_count < len(app_elements):
      raise NebraskaErrorInvalidRequest(
          "Client request omits update_check tag for more than one, but not all"
          " app requests.")

    is_install = noop_count == 1

    app_requests = []
    for app in app_elements:
      appid = app.get(self.APPID_ATTR)
      version = app.get(self.VERSION_ATTR)
      delta_okay = app.get(self.DELTA_OKAY_ATTR) == "true"

      event = app.find(self.EVENT_TAG)
      if event is not None:
        event_type = event.get(self.EVENT_TYPE_ATTR)
        event_result = event.get(self.EVENT_RESULT_ATTR, 0)
      else:
        event_type = None
        event_result = None

      ping = app.find(self.PING_TAG) is not None

      if app.find(self.UPDATE_CHECK_TAG) is not None:
        if is_install:
          request_type = Request.AppRequest.RequestType.INSTALL
        else:
          request_type = Request.AppRequest.RequestType.UPDATE
      else:
        request_type = Request.AppRequest.RequestType.NO_OP

      app_request = Request.AppRequest(
          request_type=request_type,
          appid=appid,
          ping=ping,
          version=version,
          delta_okay=delta_okay,
          event_type=event_type,
          event_result=event_result)

      if not app_request.IsValid():
        raise NebraskaErrorInvalidRequest(
            'Invalid request: {}'.format(str(app_request)))

      app_requests.append(app_request)

    return app_requests

  class AppRequest(object):
    """An app request.

    Can be an update request, install request, or neither if the update check
    tag is omitted (i.e. the platform app when installing a DLC, or when a
    request is only an event), in which case we treat the request as a no-op.
    An app request can also send pings and event result information.
    """

    class RequestType(object):
      """Simple enumeration for encoding request type."""
      INSTALL = 1 # Request installation of a new app.
      UPDATE = 2 # Request update for an existing app.
      NO_OP = 3 # Request does not require a payload response.

    def __init__(self, request_type, appid, ping=False, version=None,
                 delta_okay=None, event_type=None, event_result=None):
      """Initializes a Request.

      Args:
        request_type: install, update, or no-op.
        appid: The requested appid.
        ping: True if the server should respond to a ping.
        version: Current Chrome OS version.
        delta_okay: True if an update request can accept a delta update.
        event_type: Type of event.
        event_result: Event result.

        More on event pings:
        https://github.com/google/omaha/blob/master/doc/ServerProtocolV3.md
      """
      self.request_type = request_type
      self.appid = appid
      self.ping = ping
      self.version = version
      self.delta_okay = delta_okay
      self.event_type = event_type
      self.event_result = event_result

    def __str__(self):
      """Returns a string representation of an AppRequest."""
      if self.request_type == self.RequestType.NO_OP:
        return "{}".format(self.appid)
      elif self.request_type == self.RequestType.INSTALL:
        return "install {} v{}".format(self.appid, self.version)
      elif self.request_type == self.RequestType.UPDATE:
        return "{} update {} from v{}".format(
            "delta" if self.delta_okay else "full", self.appid, self.version)

    def IsValid(self):
      """Returns true if an AppRequest is valid, False otherwise."""
      return None not in (self.request_type, self.appid, self.version)

    def MatchAppData(self, app_data):
      """Returns true iff the app matches a given client request.

      An app matches a request if the appid matches the requested appid.
      Additionally, if the app describes a delta update payload, the request
      must be able to accept delta payloads.

      Args:
        app_data: An AppData object describing a valid app data.

      Returns:
        True if the request matches the given app, False otherwise.
      """
      if self.appid != app_data.appid:
        return False

      if self.request_type == self.RequestType.UPDATE:
        if app_data.is_delta:
          return self.delta_okay
        else:
          return True

      if self.request_type == self.RequestType.INSTALL:
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

  class XMLResponseTemplates(object):
    """XML Templates"""

    RESPONSE_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
      <response protocol="3.0" server="nebraska">
        <daystart elapsed_days="" elapsed_seconds=""/>
      </response>"""

    APP_TEMPLATE = """<app appid="" status=""></app>"""

    PING_RESPONSE = """<ping status="ok"/>"""

    EVENT_RESPONSE = """<event status="ok"/>"""

    UPDATE_CHECK_TEMPLATE = """
      <updatecheck status="ok">
        <urls>
        </urls>
        <manifest version="">
          <actions>
            <action event="update" run=""/>
            <action ChromeOSVersion=""
                    ChromeVersion="1.0.0.0"
                    IsDeltaPayload=""
                    MaxDaysToScatter="14"
                    MetadataSignatureRsa=""
                    MetadataSize=""
                    event="postinstall"/>
          </actions>
          <packages>
            <package fp=""
                     hash_sha256=""
                     name=""
                     required="true"
                     size=""/>
          </packages>
        </manifest>
      </updatecheck>"""

    UPDATE_CHECK_NO_UPDATE = """<updatecheck status="noupdate"/>"""

    ERROR_NOT_FOUND = "error-unknownApplication"

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
      response_xml = ElementTree.fromstring(
          Response.XMLResponseTemplates.RESPONSE_TEMPLATE)
      response_xml.find("daystart").set("elapsed_days", str(self._elapsed_days))
      response_xml.find(
          "daystart").set("elapsed_seconds", str(self._elapsed_seconds))

      for app_request in self._request.ParseRequest():
        logging.debug("Request for appid %s", str(app_request))
        response_xml.append(
            self.AppResponse(app_request, self._properties).Compile())

    except Exception as err:
      raise NebraskaError('Failed to compile response: {}'.format(str(err)))

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

      if (self._app_request.request_type ==
          self._app_request.RequestType.INSTALL):
        self._app_data = properties.install_app_index.Find(self._app_request)
        self._err_not_found = self._app_data is None
        self._payloads_address = properties.install_payloads_address
      elif (self._app_request.request_type ==
            self._app_request.RequestType.UPDATE):
        self._app_data = properties.update_app_index.Find(self._app_request)
        self._payloads_address = properties.update_payloads_address
        # This differentiates between apps that are not in the index and apps
        # that are available, but do not have an update available. Omaha treats
        # the former as an error, whereas the latter case should result in a
        # response containing a "noupdate" tag.
        self._err_not_found = (self._app_data is None and
                               not properties.update_app_index.Contains(
                                   self._app_request))

      if self._app_data:
        logging.debug("Found matching payload: %s", str(self._app_data))
      elif self._err_not_found:
        logging.debug("No matches for appid %s", self._app_request.appid)
      elif (self._app_request.request_type ==
            self._app_request.RequestType.UPDATE):
        logging.debug("No updates available for %s", self._app_request.appid)

    def Compile(self):
      """Compiles an app description into XML format.

      Compile the app description into an ElementTree Element that can be used
      to compile a response to a client request, and ultimately converted into
      XML.

      Returns:
        An ElementTree Element instance describing an update or install payload.
      """
      app_response = ElementTree.fromstring(
          Response.XMLResponseTemplates.APP_TEMPLATE)
      app_response.set('appid', self._app_request.appid)

      if self._app_request.ping:
        app_response.append(
            ElementTree.fromstring(Response.XMLResponseTemplates.PING_RESPONSE))
      if self._app_request.event_type is not None:
        app_response.append(ElementTree.fromstring(
            Response.XMLResponseTemplates.EVENT_RESPONSE))

      if self._app_data is not None:
        app_response.set('status', 'ok')
        app_response.append(ElementTree.fromstring(
            Response.XMLResponseTemplates.UPDATE_CHECK_TEMPLATE))
        urls = app_response.find('./updatecheck/urls')
        urls.append(
            ElementTree.Element('url', attrib={'codebase':
                                               self._payloads_address}))
        manifest = app_response.find('./updatecheck/manifest')
        manifest.set('version', self._app_data.target_version)
        actions = manifest.findall('./actions/action')
        actions[0].set('run', self._app_data.name)
        actions[1].set('ChromeOSVersion', self._app_data.target_version)
        actions[1].set('IsDeltaPayload',
                       'true' if self._app_data.is_delta else 'false')
        actions[1].set('MetadataSignatureRsa',
                       self._app_data.metadata_signature)
        actions[1].set('MetadataSize', str(self._app_data.metadata_size))
        package = manifest.find('./packages/package')
        package.set('fp', "1.%s" % self._app_data.sha256_hex)
        package.set('hash_sha256', self._app_data.sha256_hex)
        package.set('name', self._app_data.name)
        package.set('size', str(self._app_data.size))
      elif self._err_not_found:
        app_response.set('status',
                         Response.XMLResponseTemplates.ERROR_NOT_FOUND)
      elif (self._app_request.request_type ==
            self._app_request.RequestType.UPDATE):
        app_response.set('status', "ok")
        app_response.append(ElementTree.fromstring(
            Response.XMLResponseTemplates.UPDATE_CHECK_NO_UPDATE))

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
      index: Dictionary of metadata describing payloads for a given appid.
    """
    self._directory = directory
    self._index = {}

  def Scan(self):
    """Invalidates the current cache and scans the directory.

    Clears the cached index and rescans the directory.
    """
    self._index.clear()

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

            if app.appid not in self._index:
              self._index[app.appid] = []
            self._index[app.appid].append(app)
        except (IOError, KeyError, ValueError) as err:
          logging.error("Failed to read app data from %s (%s)", f, str(err))
          raise
        logging.debug("Found app data: %s", str(app))

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
    # Find a list of payloads matching the client request.
    matches = [app_data for app_data in self._index.get(request.appid, []) if
               request.MatchAppData(app_data)]

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

    Checks the index for an appid matching the appid in the given request. This
    is necessary because it allows us to differentiate between the case where we
    have no new versions of an app and the case where we have no information
    about an app at all.

    Args:
      request: Describes the client request.

    Returns:
      True if the index contains any appids matching the appid given in the
      request.
    """
    return request.appid in self._index

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
        return "{} v{}: delta update from base v{}".format(
            self.appid, self.target_version, self.source_version)
      return "{} v{}: full update/install".format(
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


class Nebraska(object):
  """An instance of this class allows responding to incoming Omaha requests.

    This class has the responsibility to manufacture Omaha responses based on
    the input update requests. This should be the main point of use of the
    Nebraska. If any changes to the behavior of Nebraska is intended, like
    creating critical update responses, or messing up with firmware and kernel
    versions, new flags should be added here to add that feature.
  """
  def __init__(self, update_payloads_address, install_payloads_address=None,
               update_metadata_dir=None, install_metadata_dir=None):
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
    upa = os.path.join(update_payloads_address, '')
    ipa = (os.path.join(install_payloads_address, '')
           if install_payloads_address is not None else upa)
    uai = AppIndex(update_metadata_dir)
    iai = AppIndex(install_metadata_dir)
    uai.Scan()
    iai.Scan()

    self._properties = NebraskaProperties(upa, ipa, uai, iai)

  def GetResponseToRequest(self, request):
    """Returns the response corresponding to a request.

    Args:
      request: The string representation of the incoming request.

    Returns:
      The string representation of the created response.
    """
    return Response(Request(request), self._properties).GetXMLString()


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
      """Responds to XML-formatted Omaha requests."""
      request_len = int(self.headers.getheader('content-length'))
      request = self.rfile.read(request_len)
      logging.debug("Received request: %s", request)

      try:
        response = self.server.owner.nebraska.GetResponseToRequest(request)
      except Exception as err:
        logging.error("Failed to handle request (%s)", str(err))
        traceback.print_exc()
        self.send_error(500, "Failed to handle incoming request")
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
                      default="http://127.0.0.1:8080")
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


if __name__ == "__main__":
  sys.exit(main(sys.argv))
