# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prep everything for for the cros-fw-provision Docker Build Context."""

import os
from pathlib import Path
import shutil
import sys


sys.path.append("../../../../")

from src.docker_libs.build_libs.shared.common_artifact_prep import (  # noqa: E402 pylint: disable=import-error,wrong-import-position
    CrosArtifactPrep,
)


class CrosFWProvisionArtifactPrep(CrosArtifactPrep):
    """Prep Needed files for the cros-fw-provision Container Docker Build."""

    def __init__(self, path: str, chroot: str, sysroot: str, force_path: bool):
        """@param args (ArgumentParser): .chroot, .sysroot, .path."""
        super().__init__(
            path=path,
            chroot=chroot,
            sysroot=sysroot,
            force_path=force_path,
            service="cros-fw-provision",
        )

    def prep(self):
        """Run the steps needed to prep the container artifacts."""
        self.copy_service()
        self.copy_fw_config()
        self.copy_metadata()
        self.copy_dockercontext()

    def copy_fw_config(self):
        """Return the absolute path of the metadata files."""
        fw_config_src = Path("usr") / "share" / "ap_firmware_config" / "fw-config.json"
        fw_config_dst = os.path.join(self.full_out, "fw-config.json")
        full_md_path = os.path.join(self.chroot, fw_config_src)
        if not os.path.exists(full_md_path):
            raise SystemExit(("Path %s does not exist, failing" % full_md_path))
        print(
            f"copying from {full_md_path} to {os.path.join(self.full_out, fw_config_dst)}"
        )
        shutil.copyfile(full_md_path, os.path.join(self.full_out, fw_config_dst))
