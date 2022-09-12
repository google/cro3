#!/usr/bin/env python3

# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Entry point for cros-test cloudbuild."""


import argparse
import os
import pathlib
import shutil
import sys
import time
import traceback
from typing import Any, Dict


# Point up a few directories to make the other python modules discoverable.
sys.path.insert(1, str(pathlib.Path(__file__).parent.resolve()/'../../../'))

# pylint: disable=import-error,wrong-import-position
from src.common.exceptions import ConfigError
from src.docker_libs.build_libs.builders import DockerBuilder
from src.docker_libs.build_libs.builders import GcloudDockerBuilder
from src.docker_libs.build_libs.builders import LocalDockerBuilder
from src.docker_libs.build_libs.cros_callbox.cros_callbox_prep import (
    CrosCallBoxDockerPrepper,
)
from src.docker_libs.build_libs.cros_publish.cros_publish_prep import (
    CrosPublishDockerPrepper,
)
from src.docker_libs.build_libs.cros_test.cros_test_prep import (
    CrosTestDockerPrepper,
)
from src.docker_libs.build_libs.cros_test_finder.cros_test_finder_prep import (
    CrosTestFinderDockerPrepper,
)
from src.docker_libs.build_libs.shared.common_service_prep import (
    CommonServiceDockerPrepper,
)


# pylint: enable=import-error,wrong-import-position

# TODO: Maybe a cfg file or something. Goal is to make is
# extremely simple/easy for a user to come in and add a new dockerfile.

REGISTERED_BUILDS = {
    'cros-callbox': {
        'prepper': CrosCallBoxDockerPrepper, 'cloud': False},
    'cros-dut': {
        'prepper': CommonServiceDockerPrepper, 'cloud': False},
    'testplan': {
        'prepper': CommonServiceDockerPrepper, 'cloud': False},
    'cros-provision': {
        'prepper': CommonServiceDockerPrepper, 'cloud': False},
    'cros-test': {
        'prepper': CrosTestDockerPrepper, 'cloud': True},
    'cros-test-finder': {
        'prepper': CrosTestFinderDockerPrepper, 'cloud': False},
    'cros-servod': {
        'prepper': CommonServiceDockerPrepper, 'cloud': False},
    'cros-publish': {
        'prepper': CrosPublishDockerPrepper, 'cloud': False},
}

# There is a ~1 in 10000 err with the fetching of the base container
# adding a retry/wait for this case.
# TODO: b/237016355, mitigate this properly with a self-owned base container.
BUILD_RETRIES = 1
RETRIES_WAIT = 10
# cros-servod does not have a ebuild yet, thus is not ready for building.
# callbox is not used (and a bit heavy) so do not build until its needed.
DO_NOT_BUILD = set(['cros-servod', 'cros-callbox'])
# NOTE: when promoting a service from DO_NOT_BUILD, it should be added to
# NON_CRITICAL for atleast a short time to verify health.
NON_CRITICAL = set(
    ['cros-dut', 'cros-provision', 'cros-publish'])


def parse_local_arguments() -> argparse.Namespace:
  """Parse the CLI."""
  parser = argparse.ArgumentParser(
      description='Prep Tauto, Tast, & Services for DockerBuild.')
  parser.add_argument('chroot',
                      help='chroot (String): The chroot path to use.')
  parser.add_argument('sysroot',
                      help=' sysroot (String): The sysroot path to use.')
  parser.add_argument('--service',
                      dest='service',
                      default='cros-test',
                      help='The service to build, eg `cros-test`')
  parser.add_argument('--tags',
                      dest='tags',
                      default='',
                      help='Comma separated list of tag names')
  parser.add_argument('--output',
                      dest='output',
                      help='File to which to write ContainerImageInfo json')
  parser.add_argument('--host',
                      dest='host',
                      default=None,
                      help='Not a DUT HOST, but the gcr repo i think?')
  parser.add_argument('--project',
                      dest='project',
                      default=None,
                      help='gcr repo project')
  parser.add_argument('--labels',
                      dest='labels',
                      default='',
                      help='Zero or more key=value comma seperated strings to '
                      'apply as labels to container.')
  parser.add_argument('--build_type',
                      dest='build_type',
                      default=None,
                      help='Specify the docker build type to be used. Valid'
                      ' options are oneof: "cloud" "local".')
  parser.add_argument('--upload',
                      dest='upload',
                      action='store_true',
                      help='Upload the built image to the registry. '
                      'Flag is only valid when using localbuild. '
                      'Cloud builds will always "upload".')
  parser.add_argument('--build_all',
                      dest='build_all',
                      action='store_true',
                      help='Build all images.')
  parser.add_argument('--build_retries',
                      dest='build_retries',
                      default=BUILD_RETRIES,
                      help='How many retries per container to build.')
  parser.add_argument('--retry_wait',
                      dest='retry_wait',
                      default=RETRIES_WAIT,
                      help='How long to wait between retries.')
  args = parser.parse_intermixed_args()
  return args


def validate_args(args: argparse.Namespace):
  if args.build_type and args.build_type not in ('cloud', 'local'):
    raise ConfigError(
        '--build_type must be one of "cloud" or "local" but got '
        f'{args.build_type}')


def isCloudBuild(args: argparse.Namespace, info: Dict[str, Any]) -> Any:
  """Determine if the image should be built with cloud or local."""
  # if the args is set, use that, otherwise default to the registration value.
  if args.build_type == 'local':
    return False
  if args.build_type == 'cloud':
    return True
  return info['cloud']


def build_image(args: argparse.Namespace, service: str, output: str) -> bool:
  """Build a singular image."""
  info = REGISTERED_BUILDS.get(service, None)
  if not info:
    print(f'{service} not support in build-dockerimages yet, please '
          'register your service via instructions in the readme')
    sys.exit(1)

  prepperlib = info['prepper']
  prepper = prepperlib(
      chroot=args.chroot,
      sysroot=args.sysroot,
      tags=args.tags,
      labels=args.labels,
      service=service)

  prepper.prep_container()
  gcloud_build = isCloudBuild(args, info)
  if gcloud_build:
    prepper.build_yaml()

  builder = GcloudDockerBuilder if gcloud_build else LocalDockerBuilder
  err = False
  try:
    b = builder(
        service=service,
        dockerfile=f'{prepper.full_out_dir}/Dockerfile',
        chroot=prepper.chroot,
        tags=prepper.tags,
        output=output,
        registry_name=args.host,
        cloud_project=args.project,
        labels=prepper.labels)
    build_container(b, args)

    # Upload if requested, or an output file is given.
    if args.upload or args.output:
      b.upload_image()

  except Exception:
    # Print a traceback for debugging.
    print(f'Failed to build Docker package for {service}:\nTraceback:\n')
    traceback.print_exc()
    err = True
  finally:
    shutil.rmtree(prepper.full_out_dir)
  return err


def build_container(b: DockerBuilder, args: argparse.Namespace):
  """Call the Build command, and optionally wrap it in retries."""
  retries = args.build_retries
  while retries >= 0:
    try:
      b.build()
      return
    except Exception as e:
      if retries <= 0:
        raise e
      else:
        print(f'Build failed, will retry in {args.retry_wait} seconds:\n{e}')
        time.sleep(args.retry_wait)
    retries -= 1


def build_all_images(args: argparse.Namespace):
  """Build all registered images.

Will skip any in DO_NOT_BUILD, and will not fail if a NON_CRITICAL build
fails.
  """
  all_pass = True
  for service in REGISTERED_BUILDS:
    if service in DO_NOT_BUILD:
      continue

    outfile = f'{args.output}_{service}'
    err = build_image(args, service, outfile)
    if err:
      # If there was an error, rm the outfile (container info).
      if os.path.exists(outfile):
        os.remove(outfile)
      if service in NON_CRITICAL:
        print(f'{service} is not marked as critical so builder will not fail.')
      else:
        # Mark a critical failure, but continue to build.
        all_pass = False

  if not all_pass:
    sys.exit(1)


def main():
  """Entry point."""
  args = parse_local_arguments()
  validate_args(args)

  if args.build_all:
    build_all_images(args)
  else:
    err = build_image(args, args.service, args.output)
    if err:
      if args.service not in NON_CRITICAL:
        sys.exit(1)


if __name__ == '__main__':
  main()
