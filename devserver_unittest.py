#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Regression tests for devserver."""

import json
from xml.dom import minidom
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
import urllib2


# Paths are relative to this script's base directory.
TEST_IMAGE_PATH = 'testdata/devserver'
TEST_IMAGE_NAME = 'update.gz'
TEST_IMAGE = TEST_IMAGE_PATH + '/' + TEST_IMAGE_NAME
EXPECTED_HASH = 'kGcOinJ0vA8vdYX53FN0F5BdwfY='

# Update request based on Omaha v2 protocol format.
UPDATE_REQUEST = {}
UPDATE_REQUEST['2.0'] = """<?xml version="1.0" encoding="UTF-8"?>
<o:gupdate xmlns:o="http://www.google.com/update2/request" version="ChromeOSUpdateEngine-0.1.0.0" updaterversion="ChromeOSUpdateEngine-0.1.0.0" protocol="2.0" ismachine="1">
    <o:os version="Indy" platform="Chrome OS" sp="0.11.254.2011_03_09_1814_i686"></o:os>
    <o:app appid="{DEV-BUILD}" version="0.11.254.2011_03_09_1814" lang="en-US" track="developer-build" board="x86-generic" hardware_class="BETA DVT" delta_okay="true">
        <o:updatecheck></o:updatecheck>
        <o:event eventtype="3" eventresult="2" previousversion="0.11.216.2011_03_02_1358"></o:event>
    </o:app>
</o:gupdate>
"""

# Update request based on Omaha v3 protocol format.
UPDATE_REQUEST['3.0'] = """<?xml version="1.0" encoding="UTF-8"?>
<request version="ChromeOSUpdateEngine-0.1.0.0" updaterversion="ChromeOSUpdateEngine-0.1.0.0" protocol="3.0" ismachine="1">
    <os version="Indy" platform="Chrome OS" sp="0.11.254.2011_03_09_1814_i686"></os>
    <app appid="{DEV-BUILD}" version="0.11.254.2011_03_09_1814" lang="en-US" track="developer-build" board="x86-generic" hardware_class="BETA DVT" delta_okay="true">
        <updatecheck></updatecheck>
        <event eventtype="3" eventresult="2" previousversion="0.11.216.2011_03_02_1358"></event>
    </app>
</request>
"""

# TODO(girts): use a random available port.
UPDATE_URL = 'http://127.0.0.1:8080/update'
STATIC_URL = 'http://127.0.0.1:8080/static/archive/'
CHECK_HEALTH_URL = 'http://127.0.0.1:8080/check_health'

API_HOST_INFO_BAD_URL = 'http://127.0.0.1:8080/api/hostinfo/'
API_HOST_INFO_URL = API_HOST_INFO_BAD_URL + '127.0.0.1'

API_SET_UPDATE_BAD_URL = 'http://127.0.0.1:8080/api/setnextupdate/'
API_SET_UPDATE_URL = API_SET_UPDATE_BAD_URL + '127.0.0.1'

API_SET_UPDATE_REQUEST = 'new_update-test/the-new-update'

DEVSERVER_START_TIMEOUT = 15

class DevserverTest(unittest.TestCase):
  """Regressions tests for devserver."""

  def setUp(self):
    """Copies in testing files."""

    # Copy in developer-test.gz, as "static/" directory is hardcoded, and it
    # would be very hard to change it (static file serving is handled deep
    # inside webpy).
    self.test_data_path = tempfile.mkdtemp()
    self.src_dir = os.path.dirname(__file__)
    self.image_src = os.path.join(self.src_dir, TEST_IMAGE)
    self.image = os.path.join(self.test_data_path, TEST_IMAGE_NAME)
    shutil.copy(self.image_src, self.image)
    self.devserver_process = self._StartServer()

  def tearDown(self):
    """Removes testing files."""
    shutil.rmtree(self.test_data_path)
    os.kill(self.devserver_process.pid, signal.SIGKILL)

  # Helper methods begin here.

  def _StartServer(self):
    """Starts devserver, returns process."""
    cmd = [
        'python',
        os.path.join(self.src_dir, 'devserver.py'),
        'devserver.py',
        '--archive_dir',
        self.test_data_path,
        ]

    process = subprocess.Popen(cmd,
                               stderr=subprocess.PIPE)

    # wait for devserver to start
    current_time = time.time()
    deadline = current_time + DEVSERVER_START_TIMEOUT
    while current_time < deadline:
      current_time = time.time()
      try:
        urllib2.urlopen(CHECK_HEALTH_URL, timeout=0.05)
        break
      except Exception:
        continue
    else:
      self.fail('Devserver failed to start within timeout.')

    return process

  def VerifyHandleUpdate(self, protocol):
    """Tests running the server and getting an update for the given protocol."""
    request = urllib2.Request(UPDATE_URL, UPDATE_REQUEST[protocol])
    connection = urllib2.urlopen(request)
    response = connection.read()
    connection.close()
    self.assertNotEqual('', response)

    # Parse the response and check if it contains the right result.
    dom = minidom.parseString(response)
    update = dom.getElementsByTagName('updatecheck')[0]
    if protocol == '2.0':
      url = self.VerifyV2Response(update)
    else:
      url = self.VerifyV3Response(update)

    # Try to fetch the image.
    connection = urllib2.urlopen(url)
    contents = connection.read()
    connection.close()
    self.assertEqual('Developers, developers, developers!\n', contents)

  def VerifyV2Response(self, update):
    """Verifies the update DOM from a v2 response and returns the url."""
    codebase = update.getAttribute('codebase')
    self.assertEqual(STATIC_URL + TEST_IMAGE_NAME, codebase)

    hash_value = update.getAttribute('hash')
    self.assertEqual(EXPECTED_HASH, hash_value)
    return codebase

  def VerifyV3Response(self, update):
    """Verifies the update DOM from a v3 response and returns the url."""
    # Parse the response and check if it contains the right result.
    urls = update.getElementsByTagName('urls')[0]
    url = urls.getElementsByTagName('url')[0]

    codebase = url.getAttribute('codebase')
    self.assertEqual(STATIC_URL, codebase)

    manifest = update.getElementsByTagName('manifest')[0]
    packages = manifest.getElementsByTagName('packages')[0]
    package = packages.getElementsByTagName('package')[0]
    filename = package.getAttribute('name')
    self.assertEqual(TEST_IMAGE_NAME, filename)

    hash_value = package.getAttribute('hash')
    self.assertEqual(EXPECTED_HASH, hash_value)

    url = os.path.join(codebase, filename)
    return url

  # Tests begin here.
  def testHandleUpdateV2(self):
    self.VerifyHandleUpdate('2.0')

  def testHandleUpdateV3(self):
    self.VerifyHandleUpdate('3.0')

  def testApiBadSetNextUpdateRequest(self):
    """Tests sending a bad setnextupdate request."""
    # Send bad request and ensure it fails...
    try:
      request = urllib2.Request(API_SET_UPDATE_URL, '')
      connection = urllib2.urlopen(request)
      connection.read()
      connection.close()
      self.fail('Invalid setnextupdate request did not fail!')
    except urllib2.URLError:
      pass

  def testApiBadSetNextUpdateURL(self):
    """Tests contacting a bad setnextupdate url."""
    # Send bad request and ensure it fails...
    try:
      connection = urllib2.urlopen(API_SET_UPDATE_BAD_URL)
      connection.read()
      connection.close()
      self.fail('Invalid setnextupdate url did not fail!')
    except urllib2.URLError:
      pass

  def testApiBadHostInfoURL(self):
    """Tests contacting a bad hostinfo url."""
    # Send bad request and ensure it fails...
    try:
      connection = urllib2.urlopen(API_HOST_INFO_BAD_URL)
      connection.read()
      connection.close()
      self.fail('Invalid hostinfo url did not fail!')
    except urllib2.URLError:
      pass

  def testApiHostInfoAndSetNextUpdate(self):
    """Tests using the setnextupdate and hostinfo api commands."""
    # Send setnextupdate command.
    request = urllib2.Request(API_SET_UPDATE_URL, API_SET_UPDATE_REQUEST)
    connection = urllib2.urlopen(request)
    response = connection.read()
    connection.close()

    # Send hostinfo command and verify the setnextupdate worked.
    connection = urllib2.urlopen(API_HOST_INFO_URL)
    response = connection.read()
    connection.close()

    self.assertEqual(
        json.loads(response)['forced_update_label'], API_SET_UPDATE_REQUEST)


if __name__ == '__main__':
  unittest.main()
