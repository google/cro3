#!/usr/bin/python

# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Integration tests for the devserver.

This module is responsible for testing the actual devserver APIs and should be
run whenever changes are made to the devserver.

Note there are two classes of tests here and they can be run separately.

To just run the short-running "unittests" run:
  ./devserver_integration_tests.py DevserverUnittests

To just run the longer-running tests, run:
  ./devserver_integration_tests.py DevserverIntegrationTests
"""

import devserver_constants
import json
import logging
from xml.dom import minidom
import os
import psutil
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
import urllib2


# Paths are relative to this script's base directory.
LABEL = 'devserver'
TEST_IMAGE_PATH = 'testdata/devserver'
TEST_IMAGE_NAME = 'update.gz'
EXPECTED_HASH = 'kGcOinJ0vA8vdYX53FN0F5BdwfY='

# Update request based on Omaha v3 protocol format.
UPDATE_REQUEST = """<?xml version="1.0" encoding="UTF-8"?>
<request version="ChromeOSUpdateEngine-0.1.0.0" updaterversion="ChromeOSUpdateEngine-0.1.0.0" protocol="3.0" ismachine="1">
    <os version="Indy" platform="Chrome OS" sp="0.11.254.2011_03_09_1814_i686"></os>
    <app appid="{DEV-BUILD}" version="11.254.2011_03_09_1814" lang="en-US" track="developer-build" board="x86-generic" hardware_class="BETA DVT" delta_okay="true">
        <updatecheck></updatecheck>
    </app>
</request>
"""

# RPC constants.
STAGE = 'stage'
IS_STAGED = 'is_staged'
STATIC = 'static'
UPDATE = 'update'
CHECK_HEALTH = 'check_health'
CONTROL_FILES = 'controlfiles'
XBUDDY = 'xbuddy'

# API rpcs and constants.
API_HOST_INFO = 'api/hostinfo'
API_SET_NEXT_UPDATE = 'api/setnextupdate'
API_SET_UPDATE_REQUEST = 'new_update-test/the-new-update'
API_TEST_IP_ADDR = '127.0.0.1'

DEVSERVER_START_TIMEOUT = 15


class DevserverFailedToStart(Exception):
  """Raised if we could not start the devserver."""


class DevserverTestCommon(unittest.TestCase):
  """Class containing common logic between devserver test classes."""

  def setUp(self):
    """Copies in testing files."""
    self.test_data_path = tempfile.mkdtemp()
    self.src_dir = os.path.dirname(__file__)

    # Current location of testdata payload.
    image_src = os.path.join(self.src_dir, TEST_IMAGE_PATH, TEST_IMAGE_NAME)

    # Copy the payload to the location of the update label "devserver."
    os.makedirs(os.path.join(self.test_data_path, LABEL))
    shutil.copy(image_src, os.path.join(self.test_data_path, LABEL,
                                        TEST_IMAGE_NAME))

    # Copy the payload to the location of forced label.
    os.makedirs(os.path.join(self.test_data_path, API_SET_UPDATE_REQUEST))
    shutil.copy(image_src, os.path.join(self.test_data_path,
                                        API_SET_UPDATE_REQUEST,
                                        TEST_IMAGE_NAME))

    self.pidfile = tempfile.mktemp('devserver_unittest')
    self.logfile = tempfile.mktemp('devserver_unittest')

    # Devserver url set in start server.
    self.devserver_url = None
    self.pid = self._StartServer()

  def tearDown(self):
    """Removes testing files."""
    shutil.rmtree(self.test_data_path)
    if self.pid:
      os.kill(self.pid, signal.SIGKILL)

    if os.path.exists(self.pidfile):
      os.remove(self.pidfile)

  # Helper methods begin here.

  def _StartServerOnPort(self, port):
    """Attempts to start devserver on |port|.

    Returns:
      The pid of the devserver.

    Raises:
      DevserverFailedToStart: If the devserver could not be started.
    """
    cmd = [
        'python',
        os.path.join(self.src_dir, 'devserver.py'),
        'devserver.py',
        '--static_dir', self.test_data_path,
        '--pidfile', self.pidfile,
        '--port', str(port),
        '--logfile', self.logfile]

    # Pipe all output. Use logfile to get devserver log.
    subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)

    # wait for devserver to start
    current_time = time.time()
    deadline = current_time + DEVSERVER_START_TIMEOUT
    while current_time < deadline:
      current_time = time.time()
      try:
        self.devserver_url = 'http://127.0.0.1:%d' % port
        self._MakeRPC(CHECK_HEALTH, timeout=0.1)
        break
      except Exception:
        continue
    else:
      raise DevserverFailedToStart('Devserver failed to start within timeout.')

    if not os.path.exists(self.pidfile):
      raise DevserverFailedToStart('Devserver did not drop a pidfile.')
    else:
      pid_value = open(self.pidfile).read()
      try:
        return int(pid_value)
      except ValueError:
        raise DevserverFailedToStart('Devserver did not drop a pid in the '
                                     'pidfile.')

  def _StartServer(self):
    """Starts devserver on a port, returns pid.

    Raises:
      DevserverFailedToStart: If all attempts to start the devserver fail.
    """
    # TODO(sosa): Fixing crbug.com/308686 will allow the devserver to do this
    # for us and be cleaner.
    for port in range(8080, 8090):
      try:
        return self._StartServerOnPort(port)
      except DevserverFailedToStart:
        logging.error('Devserver could not start on port %s', port)
        continue
    else:
      logging.error(open(self.logfile).read())
      raise DevserverFailedToStart('Devserver could not be started on all '
                                   'ports.')

  def VerifyHandleUpdate(self, label, use_test_payload=True):
    """Verifies that we can send an update request to the devserver.

    This method verifies (using a fake update_request blob) that the devserver
    can interpret the payload and give us back the right payload.

    Args:
      label: Label that update is served from e.g. <board>-release/<version>
      use_test_payload: If set to true, expects to serve payload under
        testdata/ and does extra checks i.e. compares hash and content of
        payload.
    Returns:
      url of the update payload if we verified the update.
    """
    update_label = '/'.join([UPDATE, label])
    response = self._MakeRPC(update_label, data=UPDATE_REQUEST)
    self.assertNotEqual('', response)

    # Parse the response and check if it contains the right result.
    dom = minidom.parseString(response)
    update = dom.getElementsByTagName('updatecheck')[0]
    expected_static_url = '/'.join([self.devserver_url, STATIC, label])
    expected_hash = EXPECTED_HASH if use_test_payload else None
    url = self.VerifyV3Response(update, expected_static_url,
                                expected_hash=expected_hash)

    # Verify the image we download is correct since we already know what it is.
    if use_test_payload:
      connection = urllib2.urlopen(url)
      contents = connection.read()
      connection.close()
      self.assertEqual('Developers, developers, developers!\n', contents)

    return url

  def VerifyV3Response(self, update, expected_static_url, expected_hash):
    """Verifies the update DOM from a v3 response and returns the url."""
    # Parse the response and check if it contains the right result.
    urls = update.getElementsByTagName('urls')[0]
    url = urls.getElementsByTagName('url')[0]

    static_url = url.getAttribute('codebase')
    # Static url's end in /.
    self.assertEqual(expected_static_url + '/', static_url)

    manifest = update.getElementsByTagName('manifest')[0]
    packages = manifest.getElementsByTagName('packages')[0]
    package = packages.getElementsByTagName('package')[0]
    filename = package.getAttribute('name')
    self.assertEqual(TEST_IMAGE_NAME, filename)

    if expected_hash:
      hash_value = package.getAttribute('hash')
      self.assertEqual(EXPECTED_HASH, hash_value)

    url = os.path.join(static_url, filename)
    return url

  def _MakeRPC(self, rpc, data=None, timeout=None, **kwargs):
    """Makes a RPC to the devserver using the kwargs and returns output.

    Args:
      data: Optional post data to send.
      timeout: Optional timeout to pass to urlopen.

    For example: localhost:8080/stage with artifact_url=blah/blah.
    """
    request = '/'.join([self.devserver_url, rpc])
    if kwargs:
      # Join the kwargs to the URL.
      request += '?' + '&'.join('%s=%s' % item for item in kwargs.iteritems())

    output = None
    try:
      # Let's log output for all rpc's without timeouts because we only
      # use timeouts to check to see if something is up and these checks tend
      # to be small and so logging it will be extremely repetitive.
      if not timeout:
        logging.info('Making request using %s', request)

      connection = urllib2.urlopen(request, data=data, timeout=timeout)
      output = connection.read()
      connection.close()
    except urllib2.HTTPError:
      raise

    return output


class DevserverUnittests(DevserverTestCommon):
  """Short running integration/unittests for the devserver (no remote deps).

  These are technically not unittests because they depend on being able to
  start a devserver locally which technically requires external resources so
  they are lumped with the remote tests here.
  """

  def testHandleUpdateV3(self):
    self.VerifyHandleUpdate(label=LABEL)

  def testApiBadSetNextUpdateRequest(self):
    """Tests sending a bad setnextupdate request."""
    # Send bad request and ensure it fails...
    self.assertRaises(urllib2.URLError,
                      self._MakeRPC,
                      '/'.join([API_SET_NEXT_UPDATE, API_TEST_IP_ADDR]))

  def testApiBadSetNextUpdateURL(self):
    """Tests contacting a bad setnextupdate url."""
    # Send bad request and ensure it fails...
    self.assertRaises(urllib2.URLError,
                      self._MakeRPC, API_SET_NEXT_UPDATE)

  def testApiBadHostInfoURL(self):
    """Tests contacting a bad hostinfo url."""
    # Host info should be invalid without a specified address.
    self.assertRaises(urllib2.URLError,
                      self._MakeRPC, API_HOST_INFO)

  def testApiHostInfoAndSetNextUpdate(self):
    """Tests using the setnextupdate and hostinfo api commands."""
    # Send setnextupdate command.
    self._MakeRPC('/'.join([API_SET_NEXT_UPDATE, API_TEST_IP_ADDR]),
                  data=API_SET_UPDATE_REQUEST)

    # Send hostinfo command and verify the setnextupdate worked.
    response = self._MakeRPC('/'.join([API_HOST_INFO, API_TEST_IP_ADDR]))

    self.assertEqual(
        json.loads(response)['forced_update_label'], API_SET_UPDATE_REQUEST)

  def testXBuddyLocalAlias(self):
    """Extensive local image xbuddy unittest.

    This test verifies all the local xbuddy logic by creating a new local folder
    with the necessary update items and verifies we can use all of them.
    """
    update_data = 'TEST UPDATE'
    image_data = 'TEST IMAGE'
    stateful_data = 'STATEFUL STUFFS'
    build_id = 'x86-generic/R32-9999.0.0-a1'
    xbuddy_path = 'x86-generic/R32-9999.0.0-a1/test'
    build_dir = os.path.join(self.test_data_path, build_id)
    os.makedirs(build_dir)
    test_image_file = os.path.join(build_dir,
                                   devserver_constants.TEST_IMAGE_FILE)
    update_file = os.path.join(build_dir, devserver_constants.UPDATE_FILE)
    stateful_file = os.path.join(build_dir, devserver_constants.STATEFUL_FILE)

    logging.info('Creating dummy files')

    for item, filename, data in zip(
        ['full_payload', 'test', 'stateful'],
        [update_file, test_image_file, stateful_file],
        [update_data, image_data, stateful_data]):
      logging.info('Creating file %s', filename)
      with open(filename, 'w') as fh:
        fh.write(data)

      xbuddy_path = '/'.join([build_id, item])
      logging.info('Testing xbuddy path %s', xbuddy_path)
      response = self._MakeRPC('/'.join([XBUDDY, xbuddy_path]))
      self.assertEqual(response, data)

      expected_dir = '/'.join([self.devserver_url, STATIC, build_id])
      response = self._MakeRPC('/'.join([XBUDDY, xbuddy_path]), return_dir=True)
      self.assertEqual(response, expected_dir)

      response = self._MakeRPC('/'.join([XBUDDY, xbuddy_path]),
                               relative_path=True)
      self.assertEqual(response, build_id)

    xbuddy_path = '/'.join([build_id, 'test'])
    logging.info('Testing for_update for %s', xbuddy_path)
    response = self._MakeRPC('/'.join([XBUDDY, xbuddy_path]), for_update=True)
    expected_path = '/'.join([self.devserver_url, UPDATE, build_id])
    self.assertTrue(response, expected_path)

    logging.info('Verifying the actual payload data')
    url = self.VerifyHandleUpdate(build_id, use_test_payload=False)
    logging.info('Verify the actual content of the update payload')
    connection = urllib2.urlopen(url)
    contents = connection.read()
    connection.close()
    self.assertEqual(update_data, contents)

  def testPidFile(self):
    """Test that using a pidfile works correctly."""
    with open(self.pidfile, 'r') as f:
      pid = f.read()

    # Let's assert some process information about the devserver.
    self.assertTrue(pid.isdigit())
    process = psutil.Process(int(pid))
    self.assertTrue(process.is_running())
    self.assertTrue('devserver.py' in process.cmdline)


class DevserverIntegrationTests(DevserverTestCommon):
  """Longer running integration tests that test interaction with Google Storage.

  Note: due to the interaction with Google Storage, these tests both require
  1) runner has access to the Google Storage bucket where builders store builds.
  2) time. These tests actually download the artifacts needed.
  """

  def testStageAndUpdate(self):
    """Tests core autotest workflow where we stage/update with a test payload.
    """
    build_id = 'x86-mario-release/R32-4810.0.0'
    archive_url = 'gs://chromeos-image-archive/%s' % build_id

    response = self._MakeRPC(IS_STAGED, archive_url=archive_url,
                             artifacts='full_payload,stateful')
    self.assertEqual(response, 'False')

    logging.info('Staging update artifacts')
    self._MakeRPC(STAGE, archive_url=archive_url,
                  artifacts='full_payload,stateful')
    logging.info('Staging complete. '
                 'Verifying files exist and are staged in the staging '
                 'directory.')
    response = self._MakeRPC(IS_STAGED, archive_url=archive_url,
                             artifacts='full_payload,stateful')
    self.assertEqual(response, 'True')
    staged_dir = os.path.join(self.test_data_path, build_id)
    self.assertTrue(os.path.isdir(staged_dir))
    self.assertTrue(os.path.exists(
        os.path.join(staged_dir, devserver_constants.UPDATE_FILE)))
    self.assertTrue(os.path.exists(
        os.path.join(staged_dir, devserver_constants.STATEFUL_FILE)))

    logging.info('Verifying we can update using the stage update artifacts.')
    self.VerifyHandleUpdate(build_id, use_test_payload=False)

  def testStageAutotestAndGetPackages(self):
    """Another autotest workflow test where we stage/update with a test payload.
    """
    build_id = 'x86-mario-release/R32-4810.0.0'
    archive_url = 'gs://chromeos-image-archive/%s' % build_id
    autotest_artifacts = 'autotest,test_suites,au_suite'
    logging.info('Staging autotest artifacts (may take a while).')
    self._MakeRPC(STAGE, archive_url=archive_url, artifacts=autotest_artifacts)

    response = self._MakeRPC(IS_STAGED, archive_url=archive_url,
                             artifacts=autotest_artifacts)
    self.assertEqual(response, 'True')

    # Verify the files exist and are staged in the staging directory.
    logging.info('Checking directories exist after we staged the files.')
    staged_dir = os.path.join(self.test_data_path, build_id)
    autotest_dir = os.path.join(staged_dir, 'autotest')
    package_dir = os.path.join(autotest_dir, 'packages')
    self.assertTrue(os.path.isdir(staged_dir))
    self.assertTrue(os.path.isdir(autotest_dir))
    self.assertTrue(os.path.isdir(package_dir))

    control_files = self._MakeRPC(CONTROL_FILES, build=build_id,
                                  suite_name='bvt')
    logging.info('Checking for known control file in bvt suite.')
    self.assertTrue('client/site_tests/platform_FilePerms/'
                    'control' in control_files)

  def testRemoteXBuddyAlias(self):
    """Another autotest workflow test where we stage/update with a test payload.
    """
    build_id = 'x86-mario-release/R32-4810.0.0'
    xbuddy_path = 'remote/x86-mario/R32-4810.0.0/full_payload'
    xbuddy_bad_path = 'remote/x86-mario/R32-9999.9999.9999'
    logging.info('Staging artifacts using xbuddy.')
    response = self._MakeRPC('/'.join([XBUDDY, xbuddy_path]), return_dir=True)

    logging.info('Verifying static url returned is valid.')
    expected_static_url = '/'.join([self.devserver_url, STATIC, build_id])
    self.assertEqual(response, expected_static_url)

    logging.info('Checking for_update returns an update_url for what we just '
                 'staged.')
    expected_update_url = '/'.join([self.devserver_url, UPDATE, build_id])
    response = self._MakeRPC('/'.join([XBUDDY, xbuddy_path]), for_update=True)
    self.assertEqual(response, expected_update_url)

    logging.info('Now give xbuddy a bad path.')
    self.assertRaises(urllib2.HTTPError,
                      self._MakeRPC,
                      '/'.join([XBUDDY, xbuddy_bad_path]))


if __name__ == '__main__':
  logging_format = '%(levelname)-8s: %(message)s'
  logging.basicConfig(level=logging.DEBUG, format=logging_format)
  unittest.main()
