# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common artifact prepper."""

import os
import shutil
import sys


# Point up a few directories to make the other python modules discoverable.
sys.path.append('../../../../')

from src.common.exceptions import (  # noqa: E402 pylint: disable=import-error,wrong-import-position
    ConfigError,
)
from src.common.exceptions import NotDirectoryException


class CrosArtifactPrep():
  """Prep Needed files for the Test Execution Container Docker Build."""

  def __init__(self,
               path: str,
               chroot: str,
               sysroot: str,
               force_path: bool,
               service: str):
    """@param args (ArgumentParser): .chroot, .sysroot, .path."""
    self.path = path
    self.chroot = chroot
    self.sysroot = sysroot
    self.force_path = force_path
    self.service = service

    self.full_autotest = ''
    self.full_bin = ''
    self.full_out = path
    self.build_path = ''
    self.chroot_bin = ''
    if self.sysroot.startswith('/'):
      self.sysroot = self.sysroot[1:]

    self.config_paths()

  def prep(self):
    """Run the steps needed to prep the container artifacts."""
    raise NotImplementedError

  def config_paths(self):
    """Build up the paths needed in local mem."""
    self.build_path = os.path.join(self.chroot, self.sysroot)
    self.full_autotest = os.path.join(self.build_path,
                                      'usr/local/build/autotest')
    self.chroot_bin = os.path.join(self.chroot, 'usr/bin')
    self.full_bin = os.path.join(self.build_path, 'usr/bin')
    self.validate_paths()
    self.prep_artifact_dir()

  def validate_paths(self):
    """Verify the paths generated are valid/exist."""
    if not os.path.isdir(self.full_autotest):
      if not os.path.exists(self.full_autotest):
        raise FileNotFoundError('Autotest path %s does not exist' %
                                self.full_autotest)
      raise NotDirectoryException('Autotest path %s is not a directory' %
                                  self.full_autotest)

    if not os.path.isdir(self.build_path):
      if not os.path.exists(self.build_path):
        raise FileNotFoundError('sysroot %s does not exist' % self.build_path)
      raise NotDirectoryException(
          'sysroot %s is not a directory' % self.build_path)

  def prep_artifact_dir(self):
    """Prepare the artifact dir. If it does not exist, create it."""
    if os.path.exists(self.full_out):
      if self.force_path:
        print(f'Deleting existing prepdir {self.full_out}')
        shutil.rmtree(self.full_out)
      else:
        raise ConfigError('outpath %s exists and force is not set.' %
                          self.full_out)
    os.makedirs(self.full_out, exist_ok=True)

  def copy_service(self):
    """Copy service needed for Docker."""
    shutil.copy(os.path.join(self.chroot_bin, self.service),
                self.full_out)

  def copy_python_protos(self):
    """Copy the python proto bindings."""
    shutil.copytree(
        os.path.join(self.chroot,
                     'usr/lib64/python3.6/site-packages/chromiumos'),
        os.path.join(self.full_out, 'chromiumos'))

  def copy_dockercontext(self):
    """Copy Docker Context needed to build the container to the output dir."""

    # TODO, dbeckett@: this is a hardcode back up to the execution dir
    # I need to figure out a better way to do this, but nothing comes to mind.
    cwd = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(cwd, '../../../../../', f'dockerfiles/{self.service}/')
    for item in os.listdir(src):
      s = os.path.join(src, item)
      d = os.path.join(self.full_out, item)
      shutil.copy2(s, d)

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


def FromSysrootPath(sysroot: str, file: str):
  return os.path.join(sysroot, file)
