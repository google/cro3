# Copyright 2022 The ChromiumOS Authors.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prep everything for for the cros-callbox Docker Build Context."""

import os
import shutil
import sys


sys.path.append('../../../../')


from src.docker_libs.build_libs.shared.common_artifact_prep import (  # noqa: E402 pylint: disable=import-error,wrong-import-position
    CrosArtifactPrep,
)


class CrosCallboxArtifactPrep(CrosArtifactPrep):
  """Prep Needed files for the Test Execution Container Docker Build."""

  def __init__(self,
               path: str,
               chroot: str,
               sysroot: str,
               force_path: bool):
    """@param args (ArgumentParser): .chroot, .sysroot, .path."""
    super().__init__(path=path, chroot=chroot, sysroot=sysroot,
                     force_path=force_path, service='cros-callbox')

  def prep(self):
    """Run the steps needed to prep the container artifacts."""
    self.copy_dockercontext()
    self.copy_libs()

  def copy_libs(self):
    """Copy python libs needed to build the container to the output dir."""
    cwd = os.path.dirname(os.path.abspath(__file__))
    src = os.path.join(cwd, '../../../../../', 'callbox', 'docker', 'cellular/')
    shutil.copytree(src, os.path.join(self.full_out, 'cellular'))
