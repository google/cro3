#!/usr/bin/env python3

# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Entry point for cros-test cloudbuild."""


import argparse
import pathlib
import shutil
import sys
import traceback

# Point up a few directories to make the other python modules discoverable.
sys.path.insert(1, str(pathlib.Path(__file__).parent.resolve()/'../../../'))

from src.docker_libs.build_libs.builders import GcloudDockerBuilder, LocalDockerBuilder  # pylint: disable=import-error,wrong-import-position
from src.docker_libs.build_libs.shared.common_service_prep import CommonServiceDockerPrepper
from src.docker_libs.build_libs.cros_test_finder.cros_test_finder_prep import CrosTestFinderDockerPrepper
from src.docker_libs.build_libs.cros_test.cros_test_prep import CrosTestDockerPrepper
from src.docker_libs.build_libs.cros_callbox.cros_callbox_prep import CrosCallBoxDockerPrepper


def parse_local_arguments():
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
  parser.add_argument('--localbuild',
                      dest='localbuild',
                      action='store_true',
                      help='Build the image locally using `Docker Build`. '
                           'Default is False, if running this locally its '
                           'recommended to use this arg.')
  args = parser.parse_intermixed_args()
  return args


# TODO: Better here too. Maybe a cfg file or something. Goal is to make is
# extremely simple/easy for a user to come in and add a new dockerfile.
lookup_ring = {'cros-callbox': CrosCallBoxDockerPrepper,
               'cros-dut': CommonServiceDockerPrepper,
               'cros-plan': CommonServiceDockerPrepper,
               'cros-provision': CommonServiceDockerPrepper,
               'cros-test': CrosTestDockerPrepper,
               'cros-test-finder': CrosTestFinderDockerPrepper,
               }


def main():
  """Entry point."""
  args = parse_local_arguments()

  prepperlib = lookup_ring.get(args.service, None)
  if not prepperlib:
    print(f'{args.service} not support in build-dockerimages yet, please '
          'register your service via instructions in the readme')
    sys.exit(1)

  prepper = prepperlib(
      chroot=args.chroot,
      sysroot=args.sysroot,
      tags=args.tags,
      labels=args.labels,
      service=args.service)

  prepper.prep_container()
  if not args.localbuild:
    prepper.build_yaml()

  builder = LocalDockerBuilder if args.localbuild else GcloudDockerBuilder

  err = False
  try:
    builder(
        service='cros-test',
        dockerfile=f'{prepper.full_out_dir}/Dockerfile',
        chroot=prepper.chroot,
        tags=prepper.tags,
        output=args.output,
        registry_name=args.host,
        cloud_project=args.project,
        labels=prepper.labels).build()

  except Exception:
    print('Failed to build Docker package for cros-test:\nTraceback:\n')
    traceback.print_exc()
    err = True
  finally:
    shutil.rmtree(prepper.full_out_dir)
    if err:
      sys.exit(1)


if __name__ == '__main__':
  main()
