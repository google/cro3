# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prep everything for for the cros-test Docker Build Context."""


import os
import shutil
import sys

sys.path.append('../../../../')

from src.docker_libs.build_libs.shared.common_artifact_prep\
  import CrosArtifactPrep  # noqa: E402 pylint: disable=import-error,wrong-import-position


class CrosTestFinderArtifactPrep(CrosArtifactPrep):
  """Prep Needed files for the Test Execution Container Docker Build."""

  def __init__(self,
               path: str,
               chroot: str,
               sysroot: str,
               force_path: bool):
    """@param args (ArgumentParser): .chroot, .sysroot, .path."""
    super().__init__(path=path, chroot=chroot, sysroot=sysroot,
                     force_path=force_path, service='cros-test-finder')

  def prep(self):
    """Run the steps needed to prep the container artifacts."""
    self.copy_service()
    self.copy_metadata()
    self.copy_dockercontext()

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
