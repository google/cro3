#!/usr/bin/python

# Copyright (c) 2010 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Regression tests for devserver."""

import json
import os
import signal
import shutil
import subprocess
import sys
import time
import unittest
import urllib2
from xml.dom import minidom

# Paths are relative to this script's base directory.
STATIC_DIR = 'static'
TEST_IMAGE_PATH = 'testdata/devserver'
TEST_IMAGE_NAME = 'developer-test.gz'
TEST_IMAGE = TEST_IMAGE_PATH + '/' + TEST_IMAGE_NAME
TEST_FACTORY_CONFIG = 'testdata/devserver/miniomaha-test.conf'
TEST_DATA_PATH = '/tmp/devserver-test'
TEST_CLIENT_PREFIX = 'ChromeOSUpdateEngine'

UPDATE_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<o:gupdate xmlns:o="http://www.google.com/update2/request" version="ChromeOSUpdateEngine-0.1.0.0" updaterversion="ChromeOSUpdateEngine-0.1.0.0" protocol="2.0" ismachine="1">
    <o:os version="Indy" platform="Chrome OS" sp="0.11.254.2011_03_09_1814_i686"></o:os>
    <o:app appid="{DEV-BUILD}" version="0.11.254.2011_03_09_1814" lang="en-US" track="developer-build" board="x86-generic" hardware_class="BETA DVT" delta_okay="true">
        <o:updatecheck></o:updatecheck>
        <o:event eventtype="3" eventresult="2" previousversion="0.11.216.2011_03_02_1358"></o:event>
    </o:app>
</o:gupdate>
"""
# TODO(girts): use a random available port.
UPDATE_URL = 'http://127.0.0.1:8080/update'

API_HOST_INFO_BAD_URL = 'http://127.0.0.1:8080/api/hostinfo/'
API_HOST_INFO_URL = API_HOST_INFO_BAD_URL + '127.0.0.1'

API_SET_UPDATE_BAD_URL = 'http://127.0.0.1:8080/api/setnextupdate/'
API_SET_UPDATE_URL = API_SET_UPDATE_BAD_URL + '127.0.0.1'

API_SET_UPDATE_REQUEST = 'new_update-test/the-new-update'

# Run all tests while being in /
base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
os.chdir("/")

class DevserverTest(unittest.TestCase):
  """Regressions tests for devserver."""

  def setUp(self):
    """Copies in testing files."""

    # Copy in developer-test.gz, as "static/" directory is hardcoded, and it
    # would be very hard to change it (static file serving is handled deep
    # inside webpy).
    self.image_src = os.path.join(base_dir, TEST_IMAGE)
    self.image = os.path.join(base_dir, STATIC_DIR, TEST_IMAGE_NAME)
    if os.path.exists(self.image):
      os.unlink(self.image)
    shutil.copy(self.image_src, self.image)

    self.factory_config = os.path.join(base_dir, TEST_FACTORY_CONFIG)

  def tearDown(self):
    """Removes testing files."""
    if os.path.exists(self.image):
      os.unlink(self.image)

  def testValidateFactoryConfig(self):
    """Tests --validate_factory_config."""
    cmd = [
        'python',
        os.path.join(base_dir, 'devserver.py'),
        '--validate_factory_config',
        '--client_prefix', TEST_CLIENT_PREFIX,
        '--factory_config', self.factory_config,
    ]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    stdout, _ = process.communicate()
    self.assertEqual(0, process.returncode)
    self.assertTrue('Config file looks good.' in stdout)

  def _StartServer(self, data_dir=''):
    """Starts devserver, returns process."""
    cmd = [
        'python',
        os.path.join(base_dir, 'devserver.py'),
        'devserver.py',
        '--client_prefix', TEST_CLIENT_PREFIX,
        '--factory_config', self.factory_config,
    ]
    if data_dir:
      cmd.append('--data_dir')
      cmd.append(data_dir)
    process = subprocess.Popen(cmd)
    return process.pid

  def testHandleUpdate(self):
    """Tests running the server and getting an update."""
    pid = self._StartServer()
    try:
      # Wait for the server to start up.
      time.sleep(1)
      request = urllib2.Request(UPDATE_URL, UPDATE_REQUEST)
      connection = urllib2.urlopen(request)
      response = connection.read()
      connection.close()
      self.assertNotEqual('', response)

      # Parse the response and check if it contains the right result.
      dom = minidom.parseString(response)
      update = dom.getElementsByTagName('updatecheck')[0]

      codebase = update.getAttribute('codebase')
      self.assertEqual('http://127.0.0.1:8080/static/' + TEST_IMAGE_NAME,
                       codebase)

      hash_value = update.getAttribute('hash')
      self.assertEqual('kGcOinJ0vA8vdYX53FN0F5BdwfY=', hash_value)

      # Try to fetch the image.
      connection = urllib2.urlopen(codebase)
      contents = connection.read()
      connection.close()
      self.assertEqual('Developers, developers, developers!\n', contents)
    finally:
      os.kill(pid, signal.SIGKILL)

  def testHandleDatadirUpdate(self):
    """Tests getting an update from a specified datadir"""
    # Push the image to the expected path where devserver picks it up.
    image_path = os.path.join(TEST_DATA_PATH, STATIC_DIR)
    if not os.path.exists(image_path):
      os.makedirs(image_path)

    foreign_image = os.path.join(image_path, TEST_IMAGE_NAME)
    if os.path.exists(foreign_image):
      os.unlink(foreign_image)
    shutil.copy(self.image_src, foreign_image)

    pid = self._StartServer(data_dir=TEST_DATA_PATH)
    try:
      # Wait for the server to start up.
      time.sleep(1)

      request = urllib2.Request(UPDATE_URL, UPDATE_REQUEST)
      connection = urllib2.urlopen(request)
      response = connection.read()
      connection.close()
      self.assertNotEqual('', response)

      # Parse the response and check if it contains the right result.
      dom = minidom.parseString(response)
      update = dom.getElementsByTagName('updatecheck')[0]

      codebase = update.getAttribute('codebase')
      self.assertEqual('http://127.0.0.1:8080/static/' + TEST_IMAGE_NAME,
                       codebase)

      hash_value = update.getAttribute('hash')
      self.assertEqual('kGcOinJ0vA8vdYX53FN0F5BdwfY=', hash_value)

      # Try to fetch the image.
      connection = urllib2.urlopen(codebase)
      contents = connection.read()
      connection.close()
      self.assertEqual('Developers, developers, developers!\n', contents)
      os.unlink(foreign_image)
    finally:
      os.kill(pid, signal.SIGKILL)

  def testApiBadSetNextUpdateRequest(self):
    """Tests sending a bad setnextupdate request."""
    pid = self._StartServer()
    try:
      # Wait for the server to start up.
      time.sleep(1)

      # Send bad request and ensure it fails...
      try:
        request = urllib2.Request(API_SET_UPDATE_URL, '')
        connection = urllib2.urlopen(request)
        connection.read()
        connection.close()
        self.fail('Invalid setnextupdate request did not fail!')
      except urllib2.URLError:
        pass
    finally:
      os.kill(pid, signal.SIGKILL)

  def testApiBadSetNextUpdateURL(self):
    """Tests contacting a bad setnextupdate url."""
    pid = self._StartServer()
    try:
      # Wait for the server to start up.
      time.sleep(1)

      # Send bad request and ensure it fails...
      try:
        connection = urllib2.urlopen(API_SET_UPDATE_BAD_URL)
        connection.read()
        connection.close()
        self.fail('Invalid setnextupdate url did not fail!')
      except urllib2.URLError:
        pass
    finally:
      os.kill(pid, signal.SIGKILL)

  def testApiBadHostInfoURL(self):
    """Tests contacting a bad hostinfo url."""
    pid = self._StartServer()
    try:
      # Wait for the server to start up.
      time.sleep(1)

      # Send bad request and ensure it fails...
      try:
        connection = urllib2.urlopen(API_HOST_INFO_BAD_URL)
        connection.read()
        connection.close()
        self.fail('Invalid hostinfo url did not fail!')
      except urllib2.URLError:
        pass
    finally:
      os.kill(pid, signal.SIGKILL)

  def testApiHostInfoAndSetNextUpdate(self):
    """Tests using the setnextupdate and hostinfo api commands."""
    pid = self._StartServer()
    try:
      # Wait for the server to start up.
      time.sleep(1)

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
    finally:
      os.kill(pid, signal.SIGKILL)


if __name__ == '__main__':
  unittest.main()
