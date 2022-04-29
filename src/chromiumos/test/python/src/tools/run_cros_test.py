#!/usr/bin/env python3

# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Run test service in the built container, mounting relevant dirs."""

import argparse
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

from google.protobuf.json_format import MessageToJson
from typing import List

# Used to import the proto stack.
sys.path.insert(1, str(pathlib.Path(__file__).parent.resolve()/'../../../../../../../../config/python'))
import chromiumos.test.lab.api.dut_pb2 as lab_protos
import chromiumos.test.lab.api.ip_endpoint_pb2 as IpEndpoint
import chromiumos.test.api.cros_test_cli_pb2 as cros_test_request
import chromiumos.test.api.test_case_pb2 as test_case
import chromiumos.test.api.test_suite_pb2 as test_suite


TEST_DIR = os.path.dirname(os.path.realpath(__file__))

TARGET = '/usr/local/cros-test/input/request.jsonproto'
RESULT_LOC = 'cros-test_result.jsonproto'
DEFAULT_IMAGE = 'kevin-postsubmit.R103-14709.0.0-63941-8816609403930587377'


def parse_local_arguments() -> argparse.Namespace:
  """Strip out arguments that are not to be passed through to runs.

  Add any arguments that should not be passed to remote test_that runs here.

  @Returns: tuple of local argument parser and remaining argv.
  """
  parser = argparse.ArgumentParser(
      description='CLI launch the given docker image & start Testservice.')
  parser.add_argument('-image',
                      dest='image',
                      default=DEFAULT_IMAGE,
                      help='the docker build to use')
  parser.add_argument('-results',
                      dest='results',
                      default=('/tmp/results/CFTtest/'),
                      help='Results volume on local fs')
  parser.add_argument('-tests',
                      dest='tests',
                      default='stub_Pass,stub_PassServer',
                      help='commma seperated list of tests to run')
  parser.add_argument('-harness',
                      dest='harness',
                      default='tauto',
                      help='harness of the test. either "tast" or "tauto"')
  parser.add_argument('-host',
                      dest='host',
                      default='localhost:2222',
                      help='hostname of dut.')


  args = parser.parse_args()
  return args


def _run(cmd: str) -> str:
  """Run the given cmd via subprocess.

  Args cmd (str): cmd to run.
  @Returns (str): string output from cmd.
  """
  out = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                         shell=True).communicate()[0]  # noqa: E126
  return out.decode()


class CrosTestCaller(object):
  """Get the Docker Container ready for testing."""

  def __init__(self,
               args: argparse.Namespace,
               ):
    """Param f (str): shadow_config.json file name."""

    # Base docker run command to build from.
    self.args = args
    self.test_request = args.tests.split(',')
    self.harness = args.harness
    self.dutAddr = args.host
    self.requestjson = self.build_requestjson()
    self.resultsDir = args.results
    self.prep()

    self.docker_cmd = 'docker run --net=host --user chromeos-test'

  def prep(self):
    """Prep the local system to run the cmd"""
    if os.path.isdir(self.args.results):
      try:
        print(f'WARNING: Removing Prior results dir {self.args.results}')
        # This can't delete results from a previous test because of
        # the permissions on some of the files made by CFT requiring sudo
        # to delete. Need to figure this one out...
        shutil.rmtree(self.args.results)
        self.resultsDir = self.args.results
        pathlib.Path(self.resultsDir).mkdir(parents=True)
      except OSError:
        prefix = os.path.dirname(self.args.results) + '/'
        self.resultsDir = tempfile.mkdtemp(prefix=prefix)
        print(f'Could not delete results dir. Will use: {self.resultsDir}')
    else:
      print(f'Making path {self.resultsDir}')
      _run(f'mkdir -p {self.resultsDir}')

    _run(f'chmod 777 -R {self.resultsDir}')
    pathlib.Path(os.path.join(self.resultsDir,
                              'cros-test')).mkdir(parents=True)
    with open(
        os.path.join(self.resultsDir, 'cros-test', 'request.json'), 'w') as wf:
      wf.write(MessageToJson(self.requestjson))

    self.image = ('us-docker.pkg.dev/cros-registry/test-services/cros-test:'
                  f'{self.args.image}')

  def run_in_background(self) -> None:
    """Add flag to run the docker command in the background (no stdout)."""
    self.docker_cmd += ' --rm --detach'

  def make_docker_cmd(self) -> None:
    """Make the `docker run` cmd."""
    self.docker_cmd = 'docker run --net=host --user chromeos-test'
    cros_test_dir = os.path.join(self.resultsDir, 'cros-test')
    ct_mount = f'-v {cros_test_dir}:/tmp/test/cros-test'
    res_mount = f'-v {self.resultsDir}:/tmp/test/results'

    self.cmd = (f'docker run {ct_mount} {res_mount} --rm --network host'
                f' {self.image} bin/bash -c "sudo --non-interactive chown'
                ' -R chromeos-test:chromeos-test /tmp/test && cros-test"')

  def build_requestjson(self):
    """Builds the request proto"""
    dut = self.build_dut_info()
    tests = self.build_test_info()
    primary = cros_test_request.CrosTestRequest.Device(dut=dut)
    f = cros_test_request.CrosTestRequest(primary=primary, test_suites=tests)
    return f

  def build_test_info(self) -> test_suite.TestSuite:
    """Build the test suite info/proto."""
    test_case_ids = []
    for test in self.test_request:
      test_case_ids.append(
          test_case.TestCase.Id(value=f'{self.harness}.{test}'))

    return [test_suite.TestSuite(
        name='adhoc local',
        test_case_ids=test_case.TestCaseIdList(test_case_ids=test_case_ids))]

  def build_dut_info(self) -> lab_protos.Dut:
    """Build the DUT proto."""
    chromeos = self.build_chromeos_info()
    dut_name = lab_protos.Dut.Id(value='test')

    dut = lab_protos.Dut(id=dut_name, chromeos=chromeos)
    return dut

  def build_chromeos_info(self) -> lab_protos.Dut.ChromeOS:
    """Build the basic chromeos dut proto."""
    endpoint = IpEndpoint.IpEndpoint(address=self.dutAddr)
    CHROMEOS = lab_protos.Dut.ChromeOS(ssh=endpoint)
    return CHROMEOS


def main() -> None:

  args = parse_local_arguments()
  f = CrosTestCaller(args)
  f.make_docker_cmd()
  print(f.cmd)
  child = subprocess.Popen(f.cmd, stdout=subprocess.PIPE,
                           shell=True)  # noqa: E126
  stdout, err = child.communicate()
  if child.returncode == 0:
    print('===============Test Passed===============')
  else:
    print('===============Test Failed Logs to Follow.===============')
    print(err)
  print(f'Check: {f.resultsDir} for full logs')


if __name__ == '__main__':
  main()
