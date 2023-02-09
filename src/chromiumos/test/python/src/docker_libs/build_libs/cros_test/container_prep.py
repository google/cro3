# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prep everything for for the cros-test Docker Build Context."""


import os
import sys


sys.path.append("../../../../")

from src.docker_libs.build_libs.shared.common_artifact_prep import (  # noqa: E402 pylint: disable=import-error,wrong-import-position
    CrosArtifactPrep,
)
from src.tools import (  # noqa: E402 pylint: disable=import-error,wrong-import-position
    container_util,
)


class CrosTestArtifactPrep(CrosArtifactPrep):
    """Prep Needed files for the Test Execution Container Docker Build."""

    def __init__(self, path: str, chroot: str, sysroot: str, force_path: bool):
        """@param args (ArgumentParser): .chroot, .sysroot, .path."""
        super().__init__(
            path=path,
            chroot=chroot,
            sysroot=sysroot,
            force_path=force_path,
            service="cros-test",
        )

    def prep(self):
        """Run the steps needed to prep the container artifacts."""
        self.create_tarball()
        self.copy_service()
        self.copy_metadata()
        self.copy_python_protos()
        self.copy_dockercontext()
        self.untar()
        self.remove_unused_deps()
        self.remove_tarball()

    def create_tarball(self):
        """Copy the Stuff."""
        builder = container_util.AutotestTarballBuilder(
            os.path.dirname(self.full_autotest), self.full_out, self.chroot
        )

        builder.BuildFullAutotestandTastTarball()

    def untar(self):
        """Untar the package prior to depl."""
        os.system(
            f"tar -xvf {self.full_out}/"
            f"autotest_server_package.tar.bz2 -C {self.full_out}"
        )

    def remove_unused_deps(self):
        UNUSED = ["chrome_test", "telemetry_dep"]
        for dep in UNUSED:
            os.system(f"rm -r {self.full_out}/autotest/client/deps/{dep}")

    def remove_tarball(self):
        """Remove the autotest tarball post untaring."""
        os.system(f"rm -r {self.full_out}/autotest_server_package.tar.bz2")
