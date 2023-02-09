# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tools to dynamically update existing containers."""
import json
import os
import pathlib
import sys
import time
from typing import List, Tuple


sys.path.insert(1, str(pathlib.Path(__file__).parent.resolve() / "../../"))
from src.common.utils import (
    run,  # pylint: disable=import-error, wrong-import-position
)


def _create_cleaned_image(
    temp_name: str, full_tag: str, tgts: list, sudo: bool
):
    # On the first attempt, delete everything we want to modify, generate a new
    # container w/ a known name.
    del_str = ""
    for item in tgts:
        del_str += f"{item[2]} "
    del_cmd = f'{"sudo " if sudo else ""}rm -r {del_str}'
    cmd = f"docker run -d --name {temp_name} {full_tag} {del_cmd}"
    _, err, code = run(cmd)
    if code != 0:
        raise Exception(f"docker run failed {err} with cmd: {cmd}")


def update_image(full_tag: str, tgts: list, sudo: bool) -> Tuple[str, str]:
    """Update the given docker tag with the tgts.

    This will specifically:
      - Run the image (fetching if needed) creating a unique name and delete
        the specified files/dirs
      - Copy the tgts from the local fs to the docker fs
      - Commit the new image (locally)
      - Return the new (sha, tag)

    tgts: [[src, dst, del_dst], [src, dst, del_dst]]
    sudo: to run the clean cmd as sudo or not.
    """
    temp_name = str(int(time.time()))

    _create_cleaned_image(temp_name, full_tag, tgts, sudo)

    # Attempt to cp everything. Retry anything that fails on the first 2 attempts.
    for item in tgts:
        for i in range(1):
            if _copy_into_docker(item, temp_name) == 0:
                break
            elif i == 0:
                print("Copy failed, will respin the container and try again")
                temp_name = _respin_image(item, temp_name)
            else:
                print("Copy into container failed 2x, giving up")
                sys.exit(1)
    print(f"docker commit {temp_name} {full_tag}_localchanges")
    out, err, code = run(f"docker commit {temp_name} {full_tag}_localchanges")
    if code == 0:
        print(f"Image update successful {out} {err}")
        return out, f"{full_tag}_localchanges"
    else:
        raise Exception(err)


def _respin_image(item: list, temp_name: str) -> str:
    """Respin a new container, rm'ing the incomplete copied artifacts."""
    sha, err, code = run(
        f"docker commit {temp_name} {temp_name}_localchangesfailed"
    )
    if code != 0:
        print("commit failed")
        sys.exit(1)

    # spin a new container, delete the failed to cp item, return the new name.
    temp_name = str(int(time.time()))
    _, err, code = run(
        f"docker run -d --name {temp_name} {sha}" f" sudo rm -r {item[2]}"
    )
    if code == 0:
        return temp_name
    else:
        print(f"Respin of container failed {err}")
        sys.exit(1)


def _copy_into_docker(item: list, temp_name: str) -> int:
    """Copy the src,dst from item into the given container."""
    src = item[0]
    dest = item[1]
    out, err, code = run(f"docker cp {src} {temp_name}:{dest}")

    cmd = f"docker cp {src} {temp_name}:{dest}"
    print(f"running {cmd}")
    if code != 0:
        print(f"Copy failed, known flake :( will retry.\n{out}\n\n{err}\n")
        print("eom")
        out, err, code = run(f"docker cp {src} {temp_name}:{dest}")
        if code != 0:
            print(f"Copy failed2, known flake :( will retry.\n{out}\n\n{err}\n")
            print("eom")
            return 1
        else:
            print("Copy retry worked.")
            return 0
    return 0


def _update_binary(name):
    """Rebuild the given binary in the local chroot."""
    # Optionally TODO, route this with the chroot_path arg.
    _, err, code = run(f"cros_sdk cros-workon --host start {name}")
    if code != 0:
        print(f"workon failed {err}")
        sys.exit(1)

    _, err, code = run(f"cros_sdk sudo emerge {name}")
    if code != 0:
        print(f"emerge failed {err}")
        sys.exit(1)


class AutotestUpdater:
    """Fix autotest stuff in image"""

    def __init__(self, board: str, chroot_path: str, sysroot_path: str):
        self.board = board
        self.chroot_path = chroot_path
        self.sysroot_path = sysroot_path
        autotest_path = "usr/local/build/autotest/"
        _sysroot_full_autotest_path = os.path.join(
            chroot_path, sysroot_path, autotest_path
        )

        print(f"Checking for {_sysroot_full_autotest_path}")

        # Check to see if the sysroot has an autotest build setup.
        self.hasboard = os.path.exists(_sysroot_full_autotest_path)
        if self.hasboard:
            self.path = _sysroot_full_autotest_path
        else:
            # If there is no board setup, use the autotest src.
            raise NotImplementedError(
                "Updating Autotest src direct not implemented"
            )

            # TODO: implement this path. Currently it doesn't work as the src
            # has a symlink outside of autotest which breaks on the docker cp.
            # Need to investigate which path to take to safely resolve this.
            self.path = os.path.join(
                os.path.dirname(chroot_path), "src/third_party/autotest/files"
            )

    def prep(self) -> List[str]:
        """If autotest is in the board build, will run a quickmerge to sync."""
        if self.hasboard:

            # While technically we should use the board, its often to use 1 sysroot
            # all autotest. So lets just use the the board from the given sysroot.
            qm_board = self.sysroot_path.split("/")[-1]
            QM = f"/mnt/host/source/chromite/bin/autotest_quickmerge --board={qm_board}"
            stdout, stderr, code = run(f"cros_sdk {QM}")

            if code != 0:
                print(f"Quickmerge failed!\n{stdout}\n{stderr}")
                raise Exception(
                    "Quickmerge failed on updating autotest artifacts."
                )
            return [self.path, "usr/local/", "/usr/local/autotest"]
        else:
            print("Not running quickmerge as there is no board setup.")
            return [self.path, "usr/local/", "/usr/local/autotest"]

    def update_metadata(self) -> List[str]:
        """Updates the autotest test metadata."""

        cmd = "python3 /mnt/host/source/src/third_party/autotest/files/utils/generate_metadata.py -autotest_path=/mnt/host/source/src/third_party/autotest/files -output_file=/mnt/host/source/chroot/tmp/autotest_metadata.pb"
        stdout, stderr, code = run(f"cros_sdk {cmd}")
        if code != 0:
            print(f"Metdata update failed failed!\n{stdout}\n{stderr}")
            raise Exception

        pl = [
            os.path.join(self.chroot_path, "tmp/autotest_metadata.pb"),
            "/tmp/test/metadata/autotest_metadata.pb",
            "/tmp/test/metadata/autotest_metadata.pb",
        ]
        print("Metadata update completed")

        return pl


class ContainerUpdater:
    """Class to update containers from local chroot changes."""

    def __init__(
        self,
        metadata: str,
        services: list,
        tast: bool,
        autotest: bool,
        chroot: str,
        board: str,
        sysroot: str = "",
    ):
        """The init.

        @Args metadata: Path to full metadata of the containers to update.
        @Args services: The services to update.
        @Args tast: Whether to update tast content or not.
        @Args autotest: Whether to update autotest content or not.
        @Args chroot: Path to local chroot.
        @Args board: Board that aligns to the given metadata.
        @Args sysroot: Path to sysroot within chroot. Eg "/build/dedede".
        """
        self.services = services
        self.tast = tast
        self.autotest = autotest
        self.chroot = chroot
        self.sysroot = sysroot
        self.board = board
        self.metadata = metadata
        self.new_md_path = f"{self.metadata}_local"
        self.payloads = {}
        print(f"UPDATING {services}, TAST: {tast}, AUTOTEST: {autotest}")

    def Update_Containers(self):
        """Update all containers based on the init config."""
        self._update_services()
        if "cros-test-finder" in self.services:
            self._update_cros_test_finder()
        if self.tast:
            self._update_tast()
        if self.autotest:
            self._update_autotest()
        self._update_from_payloads()
        return self.new_md_path

    def _update_cros_test_finder(self):
        """Update cros-test-finder, including metadata."""
        # Update Autotest Metadata
        at = AutotestUpdater(self.board, self.chroot, self.sysroot)
        autotest_metadata_payload = at.update_metadata()
        # Update Tast Metadata
        # TODO, implement tast updates
        # Maybe update others?
        if "cros-test-finder" not in self.payloads:
            self.payloads["cros-test-finder"] = []
        self.payloads["cros-test-finder"].append(autotest_metadata_payload)

    def _update_services(self):
        """Update all service binaries in the chroot."""
        for service in self.services:
            _update_binary(service)
            if service not in self.payloads:
                self.payloads[service] = []

            self.payloads[service].append(
                [
                    os.path.join(self.chroot, f"usr/bin/{service}"),
                    "usr/bin",
                    f"usr/bin/{service}",
                ]
            )

    def _update_tast(self):
        raise NotImplementedError("Tast dynamic updating WIP")

    def _update_autotest(self):
        at = AutotestUpdater(self.board, self.chroot, self.sysroot)
        payload = at.prep()
        metadata_payload = at.update_metadata()

        if "cros-test" not in self.payloads:
            self.payloads["cros-test"] = [payload, metadata_payload]
        else:
            self.payloads["cros-test"].append(payload)
            self.payloads["cros-test"].append(metadata_payload)

    def _get_tag(self, service: str):
        """Get the tag for the container from the metadata.

        TODO: Parse using the proto instead of a dict probs.

        @Args service: the service to get the tag for. Eg 'cros-test'.
        """
        with open(self.metadata, "r") as rf:
            containers = json.load(rf)
        _ = containers["containers"][self.board]["images"][service]["digest"]
        firstTag = containers["containers"][self.board]["images"][service][
            "tags"
        ][0]
        registryname = containers["containers"][self.board]["images"][service][
            "repository"
        ]["hostname"]
        project = containers["containers"][self.board]["images"][service][
            "repository"
        ]["project"]
        full_tag = f"{os.path.join(registryname, project, service)}:{firstTag}"
        return full_tag

    def _update_from_payloads(self):
        """Iterate through the payloads, and update the containers accordingly."""
        for service, payload in self.payloads.items():
            sha, tag = update_image(
                full_tag=self._get_tag(service),
                tgts=payload,
                sudo=service == "cros-test",
            )
            self._adjust_metadata(sha, tag, service)

    def _adjust_metadata(self, sha: str, tag: str, service: str):
        """Adjust the metadata to reflect the newly created/modded containers.

        @Args sha: sha of the updated container.
        @Args tag: full tag of the updated container.
        @Args service: The service which has been updated.
        """
        md_path = self.metadata

        # If the new md_path exists, read/re-write that instead.
        if os.path.exists(self.new_md_path):
            md_path = self.new_md_path

        with open(md_path, "r") as rf:
            containers = json.load(rf)

        # Reduce the full tag back to just the ending tag.
        registryname = containers["containers"][self.board]["images"][service][
            "repository"
        ]["hostname"]
        project = containers["containers"][self.board]["images"][service][
            "repository"
        ]["project"]
        partial_tag = tag.replace(
            f"{os.path.join(registryname, project, service)}:", ""
        )

        containers["containers"][self.board]["images"][service]["digest"] = sha
        containers["containers"][self.board]["images"][service]["tags"] = [
            partial_tag
        ]
        with open(self.new_md_path, "w") as wf:
            json.dump(containers, wf)
