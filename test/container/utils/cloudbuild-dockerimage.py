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
import subprocess
import traceback

# Point up a few directories to make the other python modules discoverable.
sys.path.insert(1, str(pathlib.Path(__file__).parent.resolve()/'../../'))

from python.docker_utils.build_helper import DockerBuilder  # pylint: disable=import-error,wrong-import-position

YAML_TEMPLATE = """
substitutions:
{subs}
steps:
- name: 'gcr.io/kaniko-project/executor:latest'
  args:
    [
      "--dockerfile=Dockerfile",
      "--context=.",
      "--cache=true",
      "--cache-ttl=366h",
{destinations}
{labels}
    ]
  timeout: 1800s
options:
  logging: CLOUD_LOGGING_ONLY
"""

SUB_VAR = '__BUILD_TAG{n}'
LABEL_SUB_VAR = '__LABEL{n}'
SUB_TEMPLATE = '  {var}: ""\n'
DESTINATION_VAR = '      "--destination=${{{var}}}",\n'
LABEL_VAR = '      "--label=${{{var}}}",\n'


def parse_local_arguments():
  """Parse the CLI."""
  parser = argparse.ArgumentParser(
      description='Prep Tauto, Tast, & Services for DockerBuild.')
  parser.add_argument('chroot',
                      help='chroot (String): The chroot path to use.')
  parser.add_argument('sysroot',
                      help=' sysroot (String): The sysroot path to use.')
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
  parser.add_argument('--local',
                      action='store_true',
                      help='Build Docker locally instead of cloud.')
  parser.add_argument('--labels',
                      dest='labels',
                      default='',
                      help='Zero or more key=value comma seperated strings to '
                           'apply as labels to container.')
  args = parser.parse_intermixed_args()
  return args


class DockerPreper():
  """Prep Needed files for the Test Execution Container Docker Build."""

  def __init__(self, args: argparse.Namespace):
    """@param args (ArgumentParser): .chroot, .sysroot, .path."""
    self.tags = args.tags.split(',') if args.tags else []
    self.labels = args.labels.split(',') if args.labels else []
    self.outputdir = 'tmp/docker/crostest'
    self.chroot = args.chroot
    self.sysroot = args.sysroot
    if self.sysroot.startswith('/'):
      self.sysroot = self.sysroot[1:]
    self.full_out_dir = os.path.join(self.chroot, self.sysroot, self.outputdir)
    self.cwd = os.path.dirname(os.path.abspath(__file__))
    self.src = os.path.join(self.cwd, '../../../../../')

  def build_yaml(self):
    subs = ''
    destinations = ''
    labels = ''

    # Always add in atleast 1 tag. If none are given, 1 will be added by the
    # builder by default, so ensure the cloudbuild yaml can support it.
    for i in range(max(len(self.tags), 1)):
      var = SUB_VAR.format(n=i)
      subs += SUB_TEMPLATE.format(var=var)
      destinations += DESTINATION_VAR.format(var=var)

    for i in range(len(self.labels)):
      var = LABEL_SUB_VAR.format(n=i)
      subs += SUB_TEMPLATE.format(var=var)
      labels += LABEL_VAR.format(var=var)

    cloudbuild_yaml = YAML_TEMPLATE.format(subs=subs,
                                           destinations=destinations,
                                           labels=labels)

    with open(os.path.join(self.full_out_dir, 'cloudbuild.yaml'), 'w') as wf:
      wf.write(cloudbuild_yaml)
      print(f'wrote yaml to {wf}')

  def prep_container(self):
    script = os.path.join(self.cwd, 'container_prep.py')
    script_call = (f'{script} -chroot={self.chroot} -sysroot={self.sysroot}'
                   f' -path={self.outputdir} -force_path=True -src={self.src}')
    subprocess.call(script_call, shell=True)


def main():
  """Entry point."""

  if not (sys.version_info.major == 3 and sys.version_info.minor >= 6):
    print('python3.6 or greater is required.')
    sys.exit(1)

  # TODO: We need to use docker-build for a local build (aka make it flag)
  # Because local builds should be taxing our gcloud builder budget
  # (and they wont even have permissions lol.)
  args = parse_local_arguments()
  preper = DockerPreper(args)
  preper.prep_container()
  preper.build_yaml()

  err = False
  try:
    builder = DockerBuilder(
        service='cros-test',
        dockerfile=f'{preper.full_out_dir}/Dockerfile',
        chroot=preper.chroot,
        tags=preper.tags,
        output=args.output,
        registry_name=args.host,
        cloud_project=args.project,
        labels=preper.labels)

    if not args.local:
      builder.gcloud_build()
    else:
      builder.docker_build()

  except Exception:
    print('Failed to build Docker package for cros-test:\nTraceback:\n')
    traceback.print_exc()
    err = True
  finally:
    shutil.rmtree(preper.full_out_dir)
    if err:
      sys.exit(1)


if __name__ == '__main__':
  main()
