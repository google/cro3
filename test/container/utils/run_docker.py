#!/usr/bin/env python3

# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Run test service in the built container, mounting relevant dirs."""
import argparse
import collections
import json
import os
import shutil
import subprocess
import tempfile


DeployConfig = collections.namedtuple(
    'DeployConfig', ['source', 'target', 'append', 'permission'])

MountConfig = collections.namedtuple(
    'MountConfig', ['source', 'target', 'mount', 'readonly', 'force_create'])


# TODO find a proper root path
TEST_DIR = os.path.dirname(os.path.realpath(__file__))

TARGET = '/usr/local/cros-test/input/request.jsonproto'
RESULT_LOC = 'cros-test_result.jsonproto'

# TODO, metadata?


def parse_local_arguments() -> argparse.Namespace:
  """Strip out arguments that are not to be passed through to runs.

  Add any arguments that should not be passed to remote test_that runs here.

  @Returns: tuple of local argument parser and remaining argv.
  """
  parser = argparse.ArgumentParser(
      description='CLI launch the given docker image & start Testservice.')
  parser.add_argument('-b', '--build', dest='build',
                      default=None,
                      help='the docker build to use')
  parser.add_argument('--results', dest='results',
                      default=os.path.join(
                          TEST_DIR, 'tmp/results/test/'),
                      help='Results volume on local fs')
  parser.add_argument('--target_results', type=str,
                      dest='target_results',
                      default='/tmp/test/results/',
                      help='Results volume on docker fs')
  parser.add_argument('-bin', '--bin', dest='bin', type=str,
                      default='cros-test',
                      help='bin to launch on Docker Run')
  parser.add_argument('--input_json', dest='input_json',
                      help='input_json to provide to cros-test')
  parser.add_argument('-output_json', dest='output_json',
                      default=RESULT_LOC,
                      help='result output json name')
  parser.add_argument('--foreground', action='store_true',
                      help='True if you want docker running in foreground.')
  parser.add_argument('--dry_run', action='store_true')

  args = parser.parse_args()
  return args


def _run(c: str) -> str:
  """Run the given cmd via subprocess.

  Args c (str): cmd to run.
  @Returns (str): string output from cmd.
  """
  out = subprocess.Popen(
      c, stdout=subprocess.PIPE, shell=True).communicate()[0]  # noqa: E126
  return out.decode()


class DockerPrepManager(object):
  """Get the Docker Container ready for testing."""

  def __init__(self, input_json: str, f: str = None):
    """Param f (str): shadow_config.json file name."""
    if f is None:
      f = 'supporting/shadow_config.json'

    self._f = f
    self.deploy_configs = []  # type:list[DeployConfig]
    self.mount_configs = []  # type:list[MountConfig]
    self.input_json = {'source': input_json,
                       'target': TARGET,
                       'append': False,
                       'permission': None}
    self._load_config()
    self._load_request()

    # Base docker run command to build from.
    self.docker_cmd = 'docker run --net=host --user chromeos-test'

  def run_in_background(self) -> None:
    self.docker_cmd += ' --rm --detach'

  def _load_config(self) -> None:
    """Load the config from f into local mem."""
    if not os.path.exists(self._f):
      return
    with open(self._f) as f:
      deploy_configs = json.load(f)

    # Deploy_configs are cp'd files
    self.deploy_configs = [self.validate(c) for c in deploy_configs
                           if 'append' in c]

    # mount_configs are mounted dirs
    self.mount_configs = [self.validate_mount(c) for c in deploy_configs
                          if 'mount' in c]

  def _load_request(self) -> None:
    """Load and mount the test request."""
    _run('chmod 777 {src}'.format(src=self.input_json['source']))
    self.deploy_configs.append(self.validate(self.input_json))

  def validate_path(self, deploy_config: dict):
    """Validate/correct the provided path."""
    target = deploy_config['target']
    if not os.path.isabs(target):
      raise Exception('Target path must be absolute path: %s' % target)

    source = deploy_config['source']
    if not os.path.isabs(source):
      if source.startswith('~'):
        raise Exception('Absolute paths must be provided.')
      else:
        source = os.path.join(TEST_DIR, source)

      # Update the source setting in deploy config with the updated path.
      deploy_config['source'] = source

    if not os.path.exists(source):
      print('Source %s does not exist' % source)

  def validate(self, deploy_config: dict) -> DeployConfig:
    """Validate the provided path & return in a named tuple i guess."""
    self.validate_path(deploy_config)
    return DeployConfig(**deploy_config)

  def validate_mount(self, deploy_config: dict) -> MountConfig:
    """Validate the provided mount & return in a named tuple i guess."""
    self.validate_path(deploy_config)
    c = MountConfig(**deploy_config)
    if not c.mount:
      raise Exception('`mount` must be true.')
    if not c.force_create and not os.path.exists(c.source):
      # raise Exception('other %s' % c.source)
      print('Warning mount SRC DNE on host %s' % c.source)
    return c

  def setup(self):
    """Start creating the docker cmd from the shadow_config.json."""
    for deploy_config in self.deploy_configs:
      self._append_docker_mount(deploy_config)

    for mount_config in self.mount_configs:
      if (mount_config.force_create and
          not os.path.exists(mount_config.source)):
        _run('mkdir -p %s' % mount_config.source)

      self._append_docker_volume(mount_config)

  def _append_docker_mount(self, config: DeployConfig):
    """Create a '--mount' arg to be used for docker run invocation.

    Use for <files>

    @Args: deploy_config: Config to be deployed.
    """
    f = ' --mount type=bind,source={full_src_path},' \
        'target={full_target_path}'.format(
            full_src_path=config.source,
            full_target_path=config.target)

    self.docker_cmd += f

  def _append_docker_volume(self, config: MountConfig):
    """Create a '-v' arg to be used for docker run invocation.

    Use for <folders/dirs>

    @Args: deploy_config: Config to be deployed.
    """
    f = ' -v {src}:{dest}'.format(src=config.source,
                                  dest=config.target)
    if hasattr(config, 'readonly') and config.readonly:
      f += ':ro'

    self.docker_cmd += f

  def add_results(self, src: str, tgt: str) -> str:
    """Add a resutls dir to the docker run volumes.

    Create a new one if provided/default is unavalible.
    """
    if os.path.exists(src):
      try:
        shutil.rmtree(src)
      except OSError:
        prefix = os.path.dirname(src) + '/'
        tdir = tempfile.mkdtemp(prefix=prefix)
        src = tdir

    _run('mkdir -p {src}'.format(src=src))
    _run('chmod 777 -R {src}'.format(src=src))

    r = MountConfig(source=src, target=tgt, mount=True, readonly=False,
                    force_create=True)
    self._append_docker_volume(r)
    return str(src)

  def add_docker_image_name(self, cmd: str):
    """Add the image name to run on docker run."""
    if not cmd:
      raise Exception('No Docker image specified.')
    self._add_arg(cmd)

  def _add_arg(self, cmd: str):
    """Add an arg to docker run."""
    self.docker_cmd += (' %s' % cmd)

  def add_cros_test(self, args: argparse.Namespace):
    """Add the cros-test bin & args to docker run."""
    if not args.input_json:
      raise Exception('An input file must be specified')
    cmd = '{} -input {} -output {}'.format(
        args.bin, TARGET, os.path.join(args.target_results, args.output_json))
    self._add_arg(cmd)


def main() -> None:
  args = parse_local_arguments()
  dm = DockerPrepManager(input_json=args.input_json)
  if not args.foreground:
    dm.run_in_background()
  dm.setup()
  res = dm.add_results(args.results, args.target_results)
  dm.add_docker_image_name(args.build)
  dm.add_cros_test(args)
  if not args.dry_run:
    f = _run(dm.docker_cmd)
    print('Running cros-test in container %s' % f)
    verb = 'can'
  else:
    print(f'Docker Command: \n{dm.docker_cmd}\n')
    verb = 'will'
  print(f'results {verb} be found {res}')


if __name__ == '__main__':
  main()
