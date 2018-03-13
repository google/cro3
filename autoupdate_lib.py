# Copyright (c) 2012 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Module containing common autoupdate utilities and protocol dictionaries."""

from __future__ import print_function

import base64
import binascii
import datetime
import os
import time
from xml.dom import minidom

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


# Responses for the various Omaha protocols indexed by the protocol version.
#
# Update available responses:
_UPDATE_RESPONSE = {}
_UPDATE_RESPONSE['2.0'] = """<?xml version="1.0" encoding="UTF-8"?>
  <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
    <daystart elapsed_seconds="%(time_elapsed)s"/>
    <app appid="%(appid)s" status="ok">
      <ping status="ok"/>
      <updatecheck
        ChromeOSVersion="999999.0.0"
        codebase="%(url)s"
        hash="%(sha1)s"
        sha256="%(sha256)s"
        needsadmin="false"
        size="%(size)s"
        IsDeltaPayload="%(is_delta_format)s"
        status="ok"
        %(extra_attr)s/>
    </app>
  </gupdate>"""
_UPDATE_RESPONSE['3.0'] = """<?xml version="1.0" encoding="UTF-8"?>
  <response protocol="3.0">
    <daystart elapsed_seconds="%(time_elapsed)s"/>
    <app appid="%(appid)s" status="ok">
      <ping status="ok"/>
      <updatecheck status="ok">
        <urls>
          <url codebase="%(codebase)s/"/>
        </urls>
        <manifest version="999999.0.0">
          <packages>
            <package hash="%(sha1)s" name="%(filename)s" size="%(size)s"
                     hash_sha256="%(hash_sha256)s" required="true"/>
          </packages>
          <actions>
            <action event="postinstall"
              ChromeOSVersion="999999.0.0"
              sha256="%(sha256)s"
              needsadmin="false"
              IsDeltaPayload="%(is_delta_format)s"
              %(extra_attr)s />
          </actions>
        </manifest>
      </updatecheck>
    </app>
  </response>"""

# No update responses:
_NO_UPDATE_RESPONSE = {}
_NO_UPDATE_RESPONSE['2.0'] = """<?xml version="1.0" encoding="UTF-8"?>
  <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
    <daystart elapsed_seconds="%(time_elapsed)s"/>
    <app appid="%(appid)s" status="ok">
      <ping status="ok"/>
      <updatecheck status="noupdate"/>
    </app>
  </gupdate>"""
_NO_UPDATE_RESPONSE['3.0'] = """<?xml version="1.0" encoding="UTF-8"?>
  <response protocol="3.0">
    <daystart elapsed_seconds="%(time_elapsed)s"/>
    <app appid="%(appid)s" status="ok">
      <ping status="ok"/>
      <updatecheck status="noupdate"/>
    </app>
  </response>"""


# Non-update event responses:
_EVENT_RESPONSE = {}
_EVENT_RESPONSE['2.0'] = """<?xml version="1.0" encoding="UTF-8"?>
  <gupdate xmlns="http://www.google.com/update2/response" protocol="2.0">
    <daystart elapsed_seconds="%(time_elapsed)s"/>
    <app appid="%(appid)s" status="ok">
      <ping status="ok"/>
      <event status="ok"/>
    </app>
  </gupdate>"""
_EVENT_RESPONSE['3.0'] = """<?xml version="1.0" encoding="UTF-8"?>
  <response protocol="3.0">
    <daystart elapsed_seconds="%(time_elapsed)s"/>
    <app appid="%(appid)s" status="ok">
      <ping status="ok"/>
      <event status="ok"/>
    </app>
  </response>"""


class UnknownProtocolRequestedException(Exception):
  """Raised when an supported protocol is specified."""


def GetSecondsSinceMidnight():
  """Returns the seconds since midnight as a decimal value."""
  now = time.localtime()
  return now[3] * 3600 + now[4] * 60 + now[5]


def GetCommonResponseValues(appid):
  """Returns a dictionary of default values for the response."""
  response_values = {}
  response_values['appid'] = appid
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


def GetUpdateResponse(sha1, sha256, size, url, is_delta_format, metadata_size,
                      signed_metadata_hash, public_key, protocol, appid,
                      critical_update=False):
  """Returns a protocol-specific response to the client for a new update.

  Args:
    sha1: SHA1 hash of update blob
    sha256: SHA256 hash of update blob
    size: size of update blob
    url: where to find update blob
    is_delta_format: true if url refers to a delta payload
    metadata_size: the size of the metadata, in bytes.
    signed_metadata_hash: the signed metadata hash or None if not signed.
    public_key: the public key to transmit to the client or None if no key.
    protocol: client's protocol version from the request Xml.
    appid: the appid associated with the response.
    critical_update: whether this is a critical update.

  Returns:
    Xml string to be passed back to client.
  """
  response_values = GetCommonResponseValues(appid)
  response_values['sha1'] = sha1
  response_values['sha256'] = sha256
  # sha256 is base64 encoded, encode it to hex.
  response_values['hash_sha256'] = binascii.hexlify(base64.b64decode(sha256))
  response_values['size'] = size
  response_values['url'] = url
  (codebase, filename) = os.path.split(url)
  response_values['codebase'] = codebase
  response_values['filename'] = filename
  response_values['is_delta_format'] = str(is_delta_format).lower()
  extra_attributes = []
  if critical_update:
    # The date string looks like '20111115' (2011-11-15). As of writing,
    # there's no particular format for the deadline value that the
    # client expects -- it's just empty vs. non-empty.
    date_str = datetime.date.today().strftime('%Y%m%d')
    extra_attributes.append('deadline="%s"' % date_str)

  if metadata_size:
    extra_attributes.append('MetadataSize="%d"' % metadata_size)
  if signed_metadata_hash:
    extra_attributes.append('MetadataSignatureRsa="%s"' % signed_metadata_hash)
  if public_key:
    extra_attributes.append('PublicKeyRsa="%s"' % public_key)

  response_values['extra_attr'] = ' '.join(extra_attributes)
  return GetSubstitutedResponse(_UPDATE_RESPONSE, protocol, response_values)


def GetNoUpdateResponse(protocol, appid):
  """Returns a protocol-specific response to the client for no update.

  Args:
    protocol: client's protocol version from the request Xml.
    appid: the appid associated with the response.

  Returns:
    Xml string to be passed back to client.
  """
  response_values = GetCommonResponseValues(appid)
  return GetSubstitutedResponse(_NO_UPDATE_RESPONSE, protocol, response_values)


def GetEventResponse(protocol, appid):
  """Returns a protocol-specific response to a client event notification.

  Args:
    protocol: client's protocol version from the request Xml.
    appid: the appid associated with the response.

  Returns:
    Xml string to be passed back to client.
  """
  response_values = GetCommonResponseValues(appid)
  return GetSubstitutedResponse(_EVENT_RESPONSE, protocol, response_values)


def ParseUpdateRequest(request_string):
  """Returns a tuple containing information parsed from an update request.

  Args:
    request_string: an xml string containing the update request.

  Returns:
    Tuple consisting of protocol string, app element, event element, and
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
