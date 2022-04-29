# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prep everything for for the cros-test Docker Build Context."""


import os
import shutil
import sys

sys.path.append('../../../../')

from src.tools import container_util  # noqa: E402


class CrosTestArtifactPrep():
  """Prep Needed files for the Test Execution Container Docker Build."""

  def __init__(self,
               path: str,
               chroot: str,
               sysroot: str,
               force_path: bool):
    """@param args (ArgumentParser): .chroot, .sysroot, .path."""
    self.path = path
    self.chroot = chroot
    self.sysroot = sysroot
    self.force_path = force_path

    self.full_autotest = ''
    self.full_bin = ''
    self.full_out = path
    self.build_path = ''
    self.chroot_bin = ''
    if self.sysroot.startswith('/'):
      self.sysroot = self.sysroot[1:]

  def prep(self):
    """Run the steps needed to prep the container artifacts."""
    self.config_paths()
    self.create_tarball()
    self.copy_services()
    self.copy_metadata()
    self.copy_dockerfiles()
    self.untar()
    self.remove_unused_deps()
    self.remove_tarball()

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
      if self.force_path:
        print(f'Deleting existing prepdir {self.full_out}')
        shutil.rmtree(self.full_out)
      else:
        raise Exception('outpath %s exists and force is not set.' %
                        self.full_out)
    os.makedirs(self.full_out, exist_ok=True)

  def create_tarball(self):
    """Copy the Stuff."""
    builder = container_util.AutotestTarballBuilder(
        os.path.dirname(self.full_autotest), self.full_out, self.chroot)

    builder.BuildFullAutotestandTastTarball()

  def untar(self):
    """Untar the package prior to depl."""
    os.system(f'tar -xvf {self.full_out}/'
              f'autotest_server_package.tar.bz2 -C {self.full_out}')

  def remove_unused_deps(self):
    UNUSED = ['chrome_test', 'telemetry_dep']
    for dep in UNUSED:
      os.system(f'rm -r {self.full_out}/autotest/client/deps/{dep}')

  def remove_tarball(self):
    """Remove the autotest tarball post untaring."""
    os.system(f'rm -r {self.full_out}/autotest_server_package.tar.bz2')

  def copy_services(self):
    """Copy services needed for Docker."""
    shutil.copy(os.path.join(self.chroot_bin, 'cros-test'),
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
      full_md_path = container_util.FromSysrootPath(self.build_path, f)
      if not os.path.exists(full_md_path):
        print('Path %s does not exist, skipping' % full_md_path)
        continue
      shutil.copyfile(full_md_path, os.path.join(self.full_out, d))

    for f, d in _CHROOT_METADATA_FILES:
      full_md_path = container_util.FromSysrootPath(self.chroot, f)
      if not os.path.exists(full_md_path):
        print('Path %s does not exist, skipping' % full_md_path)
        continue
      shutil.copyfile(full_md_path, os.path.join(self.full_out, d))

  def copy_dockerfiles(self):
    """Copy Dockerfiles needed to build the container to the output dir."""

    # TODO, this is a hardcode back up to the execution (cros-test) dir
    # I need to figure out a better way to do this, but nothing comes to mind.
    cwd = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(cwd, '../../../../../', 'dockerfiles/cros-test/')
    for item in os.listdir(src):
      s = os.path.join(src, item)
      d = os.path.join(self.full_out, item)
      shutil.copy2(s, d)
