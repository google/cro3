# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing common autoupdate utilities and protocol dictionaries."""

import datetime
import os
import time
from xml.dom import minidom


APP_ID = '87efface-864d-49a5-9bb3-4b050a7c227a'

# Responses for the various Omaha protocols indexed by the protocol version.
UPDATE_RESPONSE = {}
UPDATE_RESPONSE['2.0'] = """<?xml version="1.0" encoding="UTF-8"?>
  <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
    <daystart elapsed_seconds="%(time_elapsed)s"/>
    <app appid="{%(appid)s}" status="ok">
      <ping status="ok"/>
      <updatecheck
        ChromeOSVersion="9999.0.0"
        codebase="%(url)s"
        hash="%(sha1)s"
        sha256="%(sha256)s"
        needsadmin="false"
        size="%(size)s"
        IsDelta="%(is_delta_format)s"
        status="ok"
        %(extra_attr)s/>
    </app>
  </gupdate>
  """


UPDATE_RESPONSE['3.0'] = """<?xml version="1.0" encoding="UTF-8"?>
  <response protocol="3.0">
    <daystart elapsed_seconds="%(time_elapsed)s"/>
    <app appid="{%(appid)s}" status="ok">
      <ping status="ok"/>
      <updatecheck status="ok">
        <urls>
          <url codebase="%(codebase)s/"/>
        </urls>
        <manifest version="9999.0.0">
          <packages>
            <package hash="%(sha1)s" name="%(filename)s" size="%(size)s"
                     required="true"/>
          </packages>
          <actions>
            <action event="postinstall"
              ChromeOSVersion="9999.0.0"
              sha256="%(sha256)s"
              needsadmin="false"
              IsDelta="%(is_delta_format)s"
              %(extra_attr)s />
          </actions>
        </manifest>
      </updatecheck>
    </app>
  </response>
  """


# Responses for the various Omaha protocols indexed by the protocol version
# when there's no update to be served.
NO_UPDATE_RESPONSE = {}
NO_UPDATE_RESPONSE['2.0'] = """<?xml version="1.0" encoding="UTF-8"?>
  <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
    <daystart elapsed_seconds="%(time_elapsed)s"/>
    <app appid="{%(appid)s}" status="ok">
      <ping status="ok"/>
      <updatecheck status="noupdate"/>
    </app>
  </gupdate>
  """


NO_UPDATE_RESPONSE['3.0'] = """<?xml version="1.0" encoding="UTF-8"?>
  <response protocol="3.0">
    <daystart elapsed_seconds="%(time_elapsed)s"/>
    <app appid="{%(appid)s}" status="ok">
      <ping status="ok"/>
      <updatecheck status="noupdate"/>
    </app>
  </response>
  """


class UnknownProtocolRequestedException(Exception):
  """Raised when an supported protocol is specified."""


def GetSecondsSinceMidnight():
  """Returns the seconds since midnight as a decimal value."""
  now = time.localtime()
  return now[3] * 3600 + now[4] * 60 + now[5]


def GetCommonResponseValues():
  """Returns a dictionary of default values for the response."""
  response_values = {}
  response_values['appid'] = APP_ID
  response_values['time_elapsed'] = GetSecondsSinceMidnight()
  return response_values


def GetSubstitutedResponse(response_dict, protocol, response_values):
  """Substitutes the protocol-specific response with response_values.

  Args:
    response_dict: Canned response messages indexed by protocol.
    protocol: client's protocol version from the request Xml.
    response_values: Values to be substituted in the canned response.
  Returns:
    Xml string to be passed back to client.
  """
  response_xml = response_dict[protocol] % response_values
  return response_xml


def GetUpdateResponse(sha1, sha256, size, url, is_delta_format, protocol,
                      critical_update=False):
  """Returns a protocol-specific response to the client for a new update.

  Args:
    sha1: SHA1 hash of update blob
    sha256: SHA256 hash of update blob
    size: size of update blob
    url: where to find update blob
    is_delta_format: true if url refers to a delta payload
    protocol: client's protocol version from the request Xml.
    critical_update: whether this is a critical update.
  Returns:
    Xml string to be passed back to client.
  """
  response_values = GetCommonResponseValues()
  response_values['sha1'] = sha1
  response_values['sha256'] = sha256
  response_values['size'] = size
  response_values['url'] = url
  (codebase, filename) = os.path.split(url)
  response_values['codebase'] = codebase
  response_values['filename'] = filename
  response_values['is_delta_format'] = is_delta_format
  extra_attributes = []
  if critical_update:
    # The date string looks like '20111115' (2011-11-15). As of writing,
    # there's no particular format for the deadline value that the
    # client expects -- it's just empty vs. non-empty.
    date_str = datetime.date.today().strftime('%Y%m%d')
    extra_attributes.append('deadline="%s"' % date_str)

  response_values['extra_attr'] = ' '.join(extra_attributes)
  return GetSubstitutedResponse(UPDATE_RESPONSE, protocol, response_values)


def GetNoUpdateResponse(protocol):
  """Returns a protocol-specific response to the client for no update.

  Args:
    protocol: client's protocol version from the request Xml.
  Returns:
    Xml string to be passed back to client.
  """
  response_values = GetCommonResponseValues()
  return GetSubstitutedResponse(NO_UPDATE_RESPONSE, protocol, response_values)


def ParseUpdateRequest(request_string):
  """Returns a tuple containing information parsed from an update request.

  Args:
    request_dom: an xml string containing the update request.
  Returns tuple consisting of protocol string, app element, event element and
    update_check element.
  Raises UnknownProtocolRequestedException if we do not understand the
    protocol.
  """
  request_dom = minidom.parseString(request_string)
  protocol = request_dom.firstChild.getAttribute('protocol')
  supported_protocols = '2.0', '3.0'
  if protocol not in supported_protocols:
    raise UnknownProtocolRequestedException('Supported protocols are %s' %
                                            supported_protocols)

  element_dict = {}
  for name in ['event', 'app', 'updatecheck']:
    element_dict[name] = 'o:' + name if protocol == '2.0' else name

  app = request_dom.firstChild.getElementsByTagName(element_dict['app'])[0]
  event = request_dom.getElementsByTagName(element_dict['event'])
  update_check = request_dom.getElementsByTagName(element_dict['updatecheck'])

  return protocol, app, event, update_check
