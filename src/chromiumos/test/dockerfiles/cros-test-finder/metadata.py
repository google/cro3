#!/usr/bin/env python3

# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prep everything for for a Docker Build Context."""


import argparse

import os
import pathlib
import shutil
import sys

sys.path.insert(1, str(pathlib.Path(__file__).parent.resolve()/'../../'))

def parse_local_arguments():
  """Parse the CLI."""
  parser = argparse.ArgumentParser(
      description='Prep Tauto, Tast, & Services for DockerBuild.')
  parser.add_argument('-chroot',
                      dest='chroot',
                      help='chroot (String): The chroot path to use.')
  parser.add_argument('-sysroot',
                      dest='sysroot',
                      help=' sysroot (String): The sysroot path to use.')
  parser.add_argument('-path',
                      dest='path',
                      help='path (String): Path to write artifacts to.')
  parser.add_argument('-force_path',
                      dest='force_path',
                      default=False,
                      help='Delete anything conflicting in the outpath.')
  parser.add_argument('-src',
                      dest='src',
                      help='path (String): The src tree path.')

  args = parser.parse_args()
  return args


class DockerPrep():
  """Prep Needed files for the Test Execution Container Docker Build."""

  def __init__(self, args):
    """@param args (ArgumentParser): .chroot, .sysroot, .path."""
    self.args = args
    self.full_autotest = ''
    self.full_bin = ''
    self.full_out = ''
    self.build_path = ''
    self.chroot_bin = ''
    self.chroot = self.args.chroot
    self.src_root = self.args.src
    self.sysroot = self.args.sysroot
    if self.sysroot.startswith('/'):
      self.sysroot = self.sysroot[1:]

  def config_paths(self):
    """Build up the paths needed in local mem."""
    self.build_path = os.path.join(self.chroot, self.sysroot)
    self.full_autotest = os.path.join(self.build_path,
                                      'usr/local/build/autotest')
    self.chroot_bin = os.path.join(self.chroot, 'usr/bin')
    self.full_bin = os.path.join(self.build_path, 'usr/bin')
    self.full_out = os.path.join(self.build_path, self.args.path)
    self.validate_paths()
    self.prep_artifact_dir()

  def validate_paths(self):
    """Verify the paths generated are valid/exist."""
    if not os.path.isdir(self.full_autotest):
      if not os.path.exists(self.full_autotest):
        raise Exception('Autotest path %s does not exist' %
                        self.full_autotest)
      raise Exception('Autotest path %s is not a directory' %
                      self.full_autotest)

    if not os.path.isdir(self.build_path):
      if not os.path.exists(self.build_path):
        raise Exception('sysroot %s does not exist' % self.build_path)
      raise Exception('sysroot %s is not a directory' % self.build_path)

  def prep_artifact_dir(self):
    """Prepare the artifact dir. If it does not exist, create it."""
    if os.path.exists(self.full_out):
      if self.args.force_path:
        print('Deleting existing prepdir {}'.format(self.full_out))
        shutil.rmtree(self.full_out)
      else:
        raise Exception('outpath %s exists and force is not set.' %
                        self.full_out)
    os.makedirs(self.full_out, exist_ok=True)

  def copy_services(self):
    """Copy services needed for Docker."""
    shutil.copy(os.path.join(self.chroot_bin, 'cros-test-finder'),
                self.full_out)


  def copy_metadata(self):
    """Return the absolute path of the metadata files."""
    # Relative to build
    _BUILD_METADATA_FILES = [
        ('usr/local/build/autotest/autotest_metadata.pb',
         os.path.join(self.full_out, 'autotest_metadata.pb')),
        ('usr/share/tast/metadata/local/cros.pb',
         os.path.join(self.full_out, 'local_cros.pb')),
        ('build/share/tast/metadata/local/crosint.pb',
         os.path.join(self.full_out, 'crosint.pb'))
    ]

    # relative to chroot.
    _CHROOT_METADATA_FILES = [('usr/share/tast/metadata/remote/cros.pb',
                               os.path.join(self.full_out,
                                            'remote_cros.pb'))]

    for f, d in _BUILD_METADATA_FILES:
      full_md_path = FromSysrootPath(self.build_path, f)
      if not os.path.exists(full_md_path):
        print('Path %s does not exist, skipping' % full_md_path)
        continue
      shutil.copyfile(full_md_path, os.path.join(self.full_out, d))

    for f, d in _CHROOT_METADATA_FILES:
      full_md_path = FromSysrootPath(self.chroot, f)
      if not os.path.exists(full_md_path):
        print('Path %s does not exist, skipping' % full_md_path)
        continue
      shutil.copyfile(full_md_path, os.path.join(self.full_out, d))

  def copy_dockerfiles(self):
    """Copy Dockerfiles needed to build the container to the output dir."""
    dockerfile_relative_dir = 'platform/dev/src/chromiumos/test/test_finder/docker'

    src = os.path.join(self.src_root, dockerfile_relative_dir)
    for item in os.listdir(src):
      s = os.path.join(src, item)
      d = os.path.join(self.full_out, item)
      shutil.copy2(s, d)


def FromSysrootPath(sysroot, file):
  return os.path.join(sysroot, file)

def main():
  """Entry point."""

  if not (sys.version_info.major == 3 and sys.version_info.minor >= 6):
    print('python3.6 or greater is required.')
    sys.exit(1)

  args = parse_local_arguments()
  builder = DockerPrep(args)
  builder.config_paths()
  builder.copy_services()
  builder.copy_metadata()
  builder.copy_dockerfiles()


if __name__ == '__main__':
  main()
