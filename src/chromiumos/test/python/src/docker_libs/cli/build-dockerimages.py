#!/usr/bin/env python3

# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Entry point for cros-test cloudbuild."""


import argparse
import os
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


# TODO: Maybe a cfg file or something. Goal is to make is
# extremely simple/easy for a user to come in and add a new dockerfile.

REGISTERED_BUILDS = {'cros-callbox': CrosCallBoxDockerPrepper,
                     'cros-dut': CommonServiceDockerPrepper,
                     'cros-plan': CommonServiceDockerPrepper,
                     'cros-provision': CommonServiceDockerPrepper,
                     'cros-test': CrosTestDockerPrepper,
                     'cros-test-finder': CrosTestFinderDockerPrepper,
                     }

DO_NOT_BUILD = set(['cros-callbox', 'cros-test-finder', 'cros-plan'])
NON_CRITICAL = set(['cros-dut', 'cros-provision'])

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
  args = parser.parse_intermixed_args()
  return args


def build_image(args, service, output):
  """Build a singular image."""
  prepperlib = REGISTERED_BUILDS.get(service, None)
  if not prepperlib:
    print(f'{service} not support in build-dockerimages yet, please '
          'register your service via instructions in the readme')
    sys.exit(1)

  prepper = prepperlib(
      chroot=args.chroot,
      sysroot=args.sysroot,
      tags=args.tags,
      labels=args.labels,
      service=service)

  prepper.prep_container()
  if not args.localbuild:
    prepper.build_yaml()

  builder = LocalDockerBuilder if args.localbuild else GcloudDockerBuilder
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

    if args.localbuild and args.upload:
      b.build(upload=True)
    else:
      b.build()

  except Exception:
    # Print a traceback for debugging.
    print(f'Failed to build Docker package for {service}:\nTraceback:\n')
    traceback.print_exc()
    err = True
  finally:
    shutil.rmtree(prepper.full_out_dir)
  return err


def build_all_images(args):
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
        print(f'{service} as not marked as critical so builder will not fail.')
      else:
        # Mark a critical failure, but continue to build.
        all_pass = False

  if not all_pass:
    sys.exit(1)


def main():
  """Entry point."""
  args = parse_local_arguments()
  if args.upload and not args.localbuild:
    raise Exception('Upload flag is only valid when localbuild is set.')

  if args.build_all:
    build_all_images(args)
  else:
    err = build_image(args, args.service, args.output)
    if err:
      if args.service not in NON_CRITICAL:
        sys.exit(1)


if __name__ == '__main__':
  main()
