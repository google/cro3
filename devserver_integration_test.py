#!/usr/bin/env python2
# -*- coding: utf-8 -*-
# Copyright (c) 2013 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Integration tests for the devserver.

This module is responsible for testing the actual devserver APIs and should be
run whenever changes are made to the devserver.

To run the integration test for devserver:
  python ./devserver_integration_test.py
"""

from __future__ import print_function

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

from string import Template

from xml.dom import minidom

import requests

from six.moves import urllib

import psutil  # pylint: disable=import-error

import setup_chromite  # pylint: disable=unused-import
from chromite.lib import cros_logging as logging
from chromite.lib import cros_update_progress
from chromite.lib.xbuddy import devserver_constants


# Paths are relative to this script's base directory.
LABEL = 'devserver'
TEST_IMAGE_PATH = 'testdata/devserver'
TEST_UPDATE_PAYLOAD_NAME = 'update.gz'
TEST_UPDATE_PAYLOAD_METADATA_NAME = 'update.gz.json'

# Update request based on Omaha v3 protocol format.
UPDATE_REQUEST = Template("""<?xml version="1.0" encoding="UTF-8"?>
<request protocol="3.0" updater="ChromeOSUpdateEngine" updaterversion="0.1.0.0" ismachine="1">
    <os version="Indy" platform="Chrome OS" sp="0.11.254.2011_03_09_1814_i686"></os>
    <app appid="$appid" version="11.254.2011_03_09_1814" lang="en-US" track="developer-build" board="x86-generic" hardware_class="BETA DVT" delta_okay="true">
        <updatecheck></updatecheck>
    </app>
</request>
""")

# RPC constants.
STAGE = 'stage'
IS_STAGED = 'is_staged'
STATIC = 'static'
UPDATE = 'update'
CHECK_HEALTH = 'check_health'
CONTROL_FILES = 'controlfiles'
XBUDDY = 'xbuddy'
LIST_IMAGE_DIR = 'list_image_dir'

# API rpcs and constants.
API_SET_UPDATE_REQUEST = 'new_update-test/the-new-update'
API_TEST_IP_ADDR = '127.0.0.1'

DEVSERVER_START_TIMEOUT = 15
DEVSERVER_START_SLEEP = 1
MAX_START_ATTEMPTS = 5


class DevserverFailedToStart(Exception):
  """Raised if we could not start the devserver."""


class DevserverTestBase(unittest.TestCase):
  """Class containing common logic between devserver test classes."""

  def setUp(self):
    """Creates and populates a test directory, temporary files."""
    self.test_data_path = tempfile.mkdtemp()
    self.src_dir = os.path.dirname(__file__)

    # Copy the payload to the location of the update label.
    self._CreateLabelAndCopyUpdatePayloadFiles(LABEL)

    # Copy the payload to the location of forced label.
    self._CreateLabelAndCopyUpdatePayloadFiles(API_SET_UPDATE_REQUEST)

    # Allocate temporary files for various devserver outputs.
    self.pidfile = self._MakeTempFile('pid')
    self.portfile = self._MakeTempFile('port')
    self.logfile = self._MakeTempFile('log')

    # Initialize various runtime values.
    self.devserver_url = self.port = self.pid = None
    self.devserver = None

  def tearDown(self):
    """Kill the server, remove the test directory and temporary files."""

    self._StopServer()

    self._RemoveFile(self.pidfile)
    self._RemoveFile(self.portfile)
    # If the unittest did not succeed, print out the devserver log.
    if sys.exc_info() != (None, None, None):
      with open(self.logfile, 'r') as f:
        logging.info('--- BEGINNING OF DEVSERVER LOG ---')
        logging.info(f.read())
        logging.info('--- ENDING OF DEVSERVER LOG ---')
    self._RemoveFile(self.logfile)
    shutil.rmtree(self.test_data_path)

  # Helper methods begin here.

  def _CreateLabelAndCopyUpdatePayloadFiles(self, label):
    """Creates a label location and copies an image to it."""
    update_dir = os.path.join(self.src_dir, TEST_IMAGE_PATH)
    label_dir = os.path.join(self.test_data_path, label)
    os.makedirs(label_dir)
    for name in (TEST_UPDATE_PAYLOAD_NAME, TEST_UPDATE_PAYLOAD_METADATA_NAME):
      shutil.copy(os.path.join(update_dir, name), label_dir)

  def _MakeTempFile(self, suffix):
    """Return path of a newly created temporary file."""
    with tempfile.NamedTemporaryFile(suffix='-devserver-%s' % suffix) as f:
      name = f.name
      f.close()

    return name

  def _RemoveFile(self, filename):
    """Removes a file if it is present."""
    if os.path.isfile(filename):
      os.remove(filename)

  def _ReadIntValueFromFile(self, path, desc):
    """Reads a string from file and returns its conversion into an integer."""
    if not os.path.isfile(path):
      raise DevserverFailedToStart('Devserver did not drop %s (%r).' %
                                   (desc, path))

    with open(path) as f:
      value_str = f.read()

    try:
      return int(value_str)
    except ValueError:
      raise DevserverFailedToStart('Devserver did not drop a valid value '
                                   'in %s (%r).' % (desc, value_str))

  def _StartServer(self, port=0):
    """Attempts to start devserver on |port|.

    In the default case where port == 0, the server will bind to an arbitrary
    available port. If successful, this method will set the devserver's pid
    (self.pid), actual listening port (self.port) and URL (self.devserver_url).

    Raises:
      DevserverFailedToStart: If the devserver could not be started.
    """
    cmd = [
        os.path.join(self.src_dir, 'devserver.py'),
        '--static_dir', self.test_data_path,
        '--pidfile', self.pidfile,
        '--portfile', self.portfile,
        '--port', str(port),
        '--logfile', self.logfile,
    ]

    # Pipe all output. Use logfile to get devserver log.
    self.devserver = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                                      stdout=subprocess.PIPE)

    # Wait for devserver to start, determining its actual serving port and URL.
    current_time = time.time()
    deadline = current_time + DEVSERVER_START_TIMEOUT
    error = None
    while current_time < deadline:
      try:
        self.port = self._ReadIntValueFromFile(self.portfile, 'portfile')
        self.devserver_url = 'http://127.0.0.1:%d' % self.port
        self._MakeRPC(CHECK_HEALTH, timeout=1)
        break
      except Exception as e:
        error = e
        time.sleep(DEVSERVER_START_SLEEP)
        current_time = time.time()
    else:
      raise DevserverFailedToStart(
          'Devserver failed to start within timeout with error: %s' % error)

    # Retrieve PID.
    self.pid = self._ReadIntValueFromFile(self.pidfile, 'pidfile')

  def _StopServer(self):
    """Stops the current running devserver."""
    if not self.pid:
      return

    self.devserver.terminate()

    # Just to flush the stdout/stderr so python3 doesn't complain about the
    # unclosed file.
    self.devserver.communicate()

    self.devserver.wait()

    self.pid = None
    self.devserver = None


  def VerifyHandleUpdate(self, label, use_test_payload=True,
                         appid='{DEV-BUILD}'):
    """Verifies that we can send an update request to the devserver.

    This method verifies (using a fake update_request blob) that the devserver
    can interpret the payload and give us back the right payload.

    Args:
      label: Label that update is served from e.g. <board>-release/<version>
      use_test_payload: If set to true, expects to serve payload under
        testdata/ and does extra checks i.e. compares hash and content of
        payload.
      appid: The APP ID of the board.

    Returns:
      url of the update payload if we verified the update.
    """
    update_label = '/'.join([UPDATE, label])
    response = self._MakeRPC(
        update_label, data=UPDATE_REQUEST.substitute({'appid': appid}),
        critical_update=True)
    self.assertNotEqual('', response)
    self.assertIn('deadline="now"', response)

    # Parse the response and check if it contains the right result.
    dom = minidom.parseString(response)
    update = dom.getElementsByTagName('updatecheck')[0]
    expected_static_url = '/'.join([self.devserver_url, STATIC, label])
    url = self.VerifyV3Response(update, expected_static_url)

    # Verify the image we download is correct since we already know what it is.
    if use_test_payload:
      connection = urllib.request.urlopen(url)
      contents = connection.read().decode('utf-8')
      connection.close()
      self.assertEqual('Developers, developers, developers!\n', contents)

    return url

  def VerifyV3Response(self, update, expected_static_url):
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
    self.assertEqual(TEST_UPDATE_PAYLOAD_NAME, filename)

    return os.path.join(static_url, filename)

  def _MakeRPC(self, rpc, data=None, timeout=None, **kwargs):
    """Makes an RPC call to the devserver.

    Args:
      rpc: The function to run on the devserver, e.g. 'stage'.
      data: Optional post data to send.
      timeout: Optional timeout to pass to urlopen.
      kwargs: Optional arguments to the function, e.g. artifact_url='foo/bar'.

    Returns:
      The function output.
    """
    request = '/'.join([self.devserver_url, rpc])
    if kwargs:
      # Join the kwargs to the URL.
      request += '?' + '&'.join('%s=%s' % (k, v) for k, v in kwargs.items())

    response = (requests.post(request, data=data, timeout=timeout) if data
                else requests.get(request, timeout=timeout))
    response.raise_for_status()
    return response.text


class AutoStartDevserverTestBase(DevserverTestBase):
  """Test base class that automatically starts the devserver."""

  def setUp(self):
    """Initialize everything, then start the server."""
    super(AutoStartDevserverTestBase, self).setUp()
    self._StartServer()


class DevserverStartTests(DevserverTestBase):
  """Test that devserver starts up correctly."""

  def testStartAnyPort(self):
    """Starts the devserver, have it bind to an arbitrary available port."""
    self._StartServer()

  def testStartSpecificPort(self):
    """Starts the devserver with a specific port."""
    for _ in range(MAX_START_ATTEMPTS):
      # This is a cheap hack to find an arbitrary unused port: we open a socket
      # and bind it to port zero, then pull out the actual port number and
      # close the socket. In all likelihood, this will leave us with an
      # available port number that we can use for starting the devserver.
      # However, this heuristic is susceptible to race conditions, hence the
      # retry loop.
      s = socket.socket()
      s.bind(('', 0))
      _, port = s.getsockname()
      s.close()

      self._StartServer(port=port)
      self._StopServer()


class DevserverBasicTests(AutoStartDevserverTestBase):
  """Short running tests for the devserver (no remote deps).

  These are technically not unittests because they depend on being able to
  start a devserver locally which technically requires external resources so
  they are lumped with the remote tests here.
  """

  def testHandleUpdateV3(self):
    self.VerifyHandleUpdate(label=LABEL)

  def testXBuddyLocalAlias(self):
    """Extensive local image xbuddy unittest.

    This test verifies all the local xbuddy logic by creating a new local folder
    with the necessary update items and verifies we can use all of them.
    """
    build_id = 'x86-generic/R32-9999.0.0-a1'
    xbuddy_path = 'x86-generic/R32-9999.0.0-a1/test'
    build_dir = os.path.join(self.test_data_path, build_id)
    os.makedirs(build_dir)

    # Writing dummy files.
    image_data = 'TEST IMAGE'
    test_image_file = os.path.join(build_dir,
                                   devserver_constants.TEST_IMAGE_FILE)
    with open(test_image_file, 'w') as f:
      f.write(image_data)

    stateful_data = 'STATEFUL STUFFS'
    stateful_file = os.path.join(build_dir, devserver_constants.STATEFUL_FILE)
    with open(stateful_file, 'w') as f:
      f.write(stateful_data)

    update_dir = os.path.join(self.src_dir, TEST_IMAGE_PATH)
    for name in (TEST_UPDATE_PAYLOAD_NAME, TEST_UPDATE_PAYLOAD_METADATA_NAME):
      shutil.copy(os.path.join(update_dir, name), build_dir)
    with open(os.path.join(build_dir, TEST_UPDATE_PAYLOAD_NAME), 'r') as f:
      update_data = f.read()

    for item, data in zip(['full_payload', 'test', 'stateful'],
                          [update_data, image_data, stateful_data]):

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
    connection = urllib.request.urlopen(url)
    contents = connection.read().decode('utf-8')
    connection.close()
    self.assertEqual(update_data, contents)

  def testPidFile(self):
    """Test that using a pidfile works correctly."""
    with open(self.pidfile, 'r') as f:
      pid = f.read()
    # Let's assert some process information about the devserver.
    self.assertTrue(pid.strip().isdigit())
    process = psutil.Process(int(pid))
    self.assertTrue(process.is_running())
    self.assertIn('./devserver.py', process.cmdline())

class DevserverExtendedTests(AutoStartDevserverTestBase):
  """Longer running integration tests that test interaction with Google Storage.

  Note: due to the interaction with Google Storage, these tests both require
  1) runner has access to the Google Storage bucket where builders store builds.
  2) time. These tests actually download the artifacts needed.
  """

  def testCrosAU(self):
    """Tests core autotest workflow where we trigger CrOS auto-update.

    It mainly tests the following API:
      a. 'get_au_status'
      b. 'handler_cleanup'
      c. 'kill_au_proc'
    """
    host_name = '100.0.0.0'
    p = subprocess.Popen(['sleep 100'], shell=True, preexec_fn=os.setsid)
    pid = os.getpgid(p.pid)
    status = 'updating'
    progress_tracker = cros_update_progress.AUProgress(host_name, pid)
    progress_tracker.WriteStatus(status)

    logging.info('Retrieving auto-update status for process %d', pid)
    response = self._MakeRPC('get_au_status', host_name=host_name, pid=pid)
    self.assertFalse(json.loads(response)['finished'])
    self.assertEqual(json.loads(response)['status'], status)

    progress_tracker.WriteStatus(cros_update_progress.FINISHED)
    logging.info('Mock auto-update process is finished')
    response = self._MakeRPC('get_au_status', host_name=host_name, pid=pid)
    self.assertTrue(json.loads(response)['finished'])
    self.assertEqual(json.loads(response)['status'],
                     cros_update_progress.FINISHED)

    logging.info('Delete auto-update track status file')
    self.assertTrue(os.path.exists(progress_tracker.track_status_file))
    self._MakeRPC('handler_cleanup', host_name=host_name, pid=pid)
    self.assertFalse(os.path.exists(progress_tracker.track_status_file))

    logging.info('Kill the left auto-update processes for host %s', host_name)
    progress_tracker.WriteStatus(cros_update_progress.FINISHED)
    response = self._MakeRPC('kill_au_proc', host_name=host_name)
    self.assertEqual(response, 'True')
    self.assertFalse(os.path.exists(progress_tracker.track_status_file))
    self.assertFalse(cros_update_progress.IsProcessAlive(pid))

    p.terminate()
    p.wait()

  def testStageAndUpdate(self):
    """Tests core stage/update autotest workflow where with a test payload."""
    build_id = 'eve-release/R78-12499.0.0'
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
        os.path.join(staged_dir, devserver_constants.UPDATE_METADATA_FILE)))
    self.assertTrue(os.path.exists(
        os.path.join(staged_dir, devserver_constants.STATEFUL_FILE)))

    logging.info('Verifying we can update using the stage update artifacts.')
    self.VerifyHandleUpdate(build_id, use_test_payload=False,
                            appid='{01906EA2-3EB2-41F1-8F62-F0B7120EFD2E}')

  @unittest.skip('crbug.com/640063 Broken test.')
  def testStageAutotestAndGetPackages(self):
    """Another stage/update autotest workflow test with a test payload."""
    build_id = 'eve-release/R69-10782.0.0'
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
    self.assertIn('client/site_tests/platform_FilePerms/control', control_files)

  def testRemoteXBuddyAlias(self):
    """Another stage/update autotest workflow test with a test payload."""
    build_id = 'eve-release/R69-10782.0.0'
    xbuddy_path = 'remote/eve/R69-10782.0.0/full_payload'
    xbuddy_bad_path = 'remote/eve/R32-9999.9999.9999'
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
    self.assertRaises(requests.exceptions.RequestException,
                      self._MakeRPC,
                      '/'.join([XBUDDY, xbuddy_bad_path]))

  def testListImageDir(self):
    """Verifies that we can list the contents of the image directory."""
    build_id = 'x86-mario-release/R32-4810.0.0'
    archive_url = 'gs://chromeos-image-archive/%s' % build_id
    build_dir = os.path.join(self.test_data_path, build_id)
    shutil.rmtree(build_dir, ignore_errors=True)

    logging.info('checking for %s on an unstaged build.', LIST_IMAGE_DIR)
    response = self._MakeRPC(LIST_IMAGE_DIR, archive_url=archive_url)
    self.assertIn(archive_url, response)
    self.assertIn('not been staged', response)

    logging.info('Checking for %s on a staged build.', LIST_IMAGE_DIR)
    fake_file_name = 'fake_file'
    try:
      os.makedirs(build_dir)
      open(os.path.join(build_dir, fake_file_name), 'w').close()
    except OSError:
      logging.error('Could not create files to imitate staged content. '
                    'Build dir %s, file %s', build_dir, fake_file_name)
      raise
    response = self._MakeRPC(LIST_IMAGE_DIR, archive_url=archive_url)
    self.assertIn(fake_file_name, response)
    shutil.rmtree(build_dir, ignore_errors=True)


if __name__ == '__main__':
  unittest.main()
