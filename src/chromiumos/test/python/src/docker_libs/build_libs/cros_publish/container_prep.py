# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Prep everything for the cros publish Docker Build Context."""

import os
import shutil
import sys

from src.common.utils import (
    run,  # pylint: disable=import-error,wrong-import-position
)
from src.docker_libs.build_libs.shared.common_artifact_prep import (  # noqa: E402 pylint: disable=import-error,wrong-import-position
    CrosArtifactPrep,
)
from src.tools import (  # noqa: E402 pylint: disable=import-error,wrong-import-position
    container_util,
)


sys.path.append("../../../../")


class CrosPublishArtifactPrep(CrosArtifactPrep):
    """Prep Needed files for the Cros Publish Container Docker Build."""

    def __init__(self, path: str, chroot: str, sysroot: str, force_path: bool):
        """@param args (ArgumentParser): .chroot, .sysroot, .path."""
        super().__init__(
            path=path,
            chroot=chroot,
            sysroot=sysroot,
            force_path=force_path,
            service="cros-publish",
        )

    def prep(self):
        """Run the steps needed to prep the container artifacts."""
        # Copy all cros-publish services
        self.copy_custom_service("gcs-publish")
        self.copy_custom_service("tko-publish")
        self.copy_custom_service("rdb-publish")
        self.copy_custom_service("cpcon-publish")

        # Copy CPCon upload dependencies
        self.copy_cpcon_upload()

        self.create_tarball()
        self.copy_dockercontext()
        self.untar()
        self.remove_extra()
        self.remove_tarball()

        # Download the required packages
        self.install_cipd_package()
        self.cipd_init()
        self.install_result_adapter_package()
        self.install_rdb_package()

    def untar(self):
        """Untar the package prior to depl."""
        os.system(
            f"tar -xvf {self.full_out}/"
            f"autotest_server_package.tar.bz2 -C {self.full_out}"
        )

    def remove_extra(self):
        """Removes not required autotest code from the bundle."""
        UNUSED = [
            "autotest/client/deps/",
            "autotest/client/site_tests/",
            "autotest/moblab/*",
            "autotest/server/site_tests/",
            "autotest/test_suites/",
            "autotest/frontend/client/src/autotest/*",
        ]
        for fn in UNUSED:
            os.system(f"rm -r {self.full_out}/{fn}")

    def create_tarball(self):
        """Copy the Stuff."""
        builder = container_util.AutotestTarballBuilder(
            os.path.dirname(self.full_autotest),
            self.full_out,
            self.chroot,
            tko_only=True,
        )

        builder.BuildFullAutotestandTastTarball()

    def remove_tarball(self):
        """Remove the autotest tarball post untaring."""
        os.system(f"rm -r {self.full_out}/autotest_server_package.tar.bz2")

    def install_cipd_package(self):
        """Install and unzip cipd package."""
        cipd_package_loc = "https://chrome-infra-packages.appspot.com/dl/infra/tools/cipd/linux-amd64/+/latest"
        downloaded_zip_name = "cipdzip.zip"
        out, err, code = run(
            f"wget -O {self.full_out}/{downloaded_zip_name} {cipd_package_loc}"
        )
        if out != "":
            print(out)
        if err != "":
            print(err)
        if code != 0:
            print("downloading cipd package failed")

        out, err, code = run(
            f"unzip -o {self.full_out}/{downloaded_zip_name} -d {self.full_out}/"
        )
        if out != "":
            print(out)
        if err != "":
            print(err)
        if code != 0:
            print("unzipping cipd package failed")

    def cipd_init(self):
        """Initialize Cipd."""

        out, err, code = run(
            f"{self.full_out}/cipd init -verbose -force {self.full_out}"
        )
        if out != "":
            print(out)
        if err != "":
            print(err)
        if code != 0:
            print("Initializing cipd failed")

    def install_result_adapter_package(self):
        """Install result_adapter package using cipd."""
        result_adapter_package = "infra/tools/result_adapter/linux-amd64"
        result_adapter_version = "prod"
        output_loc = f"{self.full_out}/result_adapter_cipd_metadata.json"

        out, err, code = run(
            f"{self.full_out}/cipd install {result_adapter_package} {result_adapter_version} -root {self.full_out} -json-output {output_loc}"
        )
        if out != "":
            print(out)
        if err != "":
            print(err)
        if code != 0:
            print("downloading result_adapter package failed")

    def install_rdb_package(self):
        """Install rdb package using cipd."""
        result_adapter_package = "infra/tools/rdb/linux-amd64"
        result_adapter_version = "latest"
        output_loc = f"{self.full_out}/rdb_cipd_metadata.json"

        out, err, code = run(
            f"{self.full_out}/cipd install {result_adapter_package} {result_adapter_version} -root {self.full_out} -json-output {output_loc}"
        )
        if out != "":
            print(out)
        if err != "":
            print(err)
        if code != 0:
            print("downloading rdb package failed")

    def copy_cpcon_upload(self):
        """Copy upload_results for CPCon upload"""
        cwd = os.path.dirname(os.path.abspath(__file__))
        src = os.path.join(cwd, "../../../../../../../../../../")
        autotest_contrib = os.path.join(
            src, "third_party", "autotest", "files", "contrib"
        )
        shutil.copytree(autotest_contrib, self.full_out + "/contrib/")
