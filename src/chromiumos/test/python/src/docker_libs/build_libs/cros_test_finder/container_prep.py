# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prep everything for for the cros-test Docker Build Context."""


import sys


sys.path.append("../../../../")

from src.docker_libs.build_libs.shared.common_artifact_prep import (  # noqa: E402 pylint: disable=import-error,wrong-import-position
    CrosArtifactPrep,
)


class CrosTestFinderArtifactPrep(CrosArtifactPrep):
    """Prep Needed files for the Test Execution Container Docker Build."""

    def __init__(self, path: str, chroot: str, sysroot: str, force_path: bool):
        """@param args (ArgumentParser): .chroot, .sysroot, .path."""
        super().__init__(
            path=path,
            chroot=chroot,
            sysroot=sysroot,
            force_path=force_path,
            service="cros-test-finder",
        )

    def prep(self):
        """Run the steps needed to prep the container artifacts."""
        self.copy_service()
        self.copy_metadata()
        self.copy_dockercontext()