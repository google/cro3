# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=no-name-in-module

"""Client side code for testing the kbuild builder interface"""

from __future__ import print_function

import logging

from common import print_msg
import grpc
from kbuild_builder_pb2 import BisectKbuildRequest
from kbuild_builder_pb2 import DutProvisionRequest
from kbuild_builder_pb2_grpc import KbuildBuilderStub


def run():
    """Main client side function"""

    print("Testing kernel build dispatcher interface ...\n")

    with grpc.insecure_channel("localhost:50051") as channel:
        stub = KbuildBuilderStub(channel)

        print("Sending BisectKbuildRequest message")
        rep = stub.CreateBisectKbuild(
            BisectKbuildRequest(
                commit_sha="d1678bf45f21fa5ae4a456f821858679556ea5f8",
                board_name="volteer-kernelnext",
                branch_name="chromeos-kernelupstream-6.2-rc3",
            )
        )
        print("Received BisectKbuildResponse message with:")
        print_msg(rep)

        print("Sending DutProvisionRequest message")
        rep = stub.ProvisionDut(
            DutProvisionRequest(
                dut_ip_address="10.77.100.101",
                kbuild_archive_path=(
                    "gs://kcr-bisection/volteer-kernelnext_chromeos-"
                    "kernelupstream-6.2-rc3_"
                    "d1678bf45f21fa5ae4a456f821858679556ea5f8.tgz"
                ),
            )
        )
        print("Received DutProvisionResponse message with:")
        print_msg(rep)


if __name__ == "__main__":
    logging.basicConfig()
    run()
