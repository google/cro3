# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=no-name-in-module

"""Client side code for testing the kbuild dispatcher interface"""

from __future__ import print_function

import logging
import uuid

from common import print_msg
import grpc
from kbuild_dispatcher_pb2 import BisectKbuildRequest
from kbuild_dispatcher_pb2 import BisectKbuildStatusRequest
from kbuild_dispatcher_pb2 import BisectSessionRequest
from kbuild_dispatcher_pb2 import DutProvisionRequest
from kbuild_dispatcher_pb2 import DutProvisionStatusRequest
from kbuild_dispatcher_pb2 import Error
from kbuild_dispatcher_pb2 import Status
from kbuild_dispatcher_pb2_grpc import KbuildDispStub


def run():
    """Main client side function"""

    print("Testing kernel build dispatcher interface ...\n")

    with grpc.insecure_channel("localhost:50051") as channel:
        stub = KbuildDispStub(channel)

        print("Sending BisectSessionRequest message")
        rep = stub.CreateBisectSession(
            BisectSessionRequest(session_id=str(uuid.uuid1()))
        )
        print("Received BisectSessionResponse message with:")
        print_msg(rep)

        print("Sending BisectKbuildRequest message")
        rep = stub.CreateBisectKbuild(
            BisectKbuildRequest(
                session_id=rep.session_id,
                commit_sha="ebddb1404900657b7f03a56ee4c34a9d218c4030",
                board_name="volteer-kernelnext",
                branch_name="chromeos-kernelupstream-6.2-rc3",
            )
        )
        print("Received BisectKbuildResponse message with:")
        print_msg(rep)

        print("Sending BisectKbuildRequest message")
        rep = stub.CreateBisectKbuild(
            BisectKbuildRequest(
                session_id=rep.session_id,
                commit_sha="d1678bf45f21fa5ae4a456f821858679556ea5f8",
                board_name="volteer-kernelnext",
                branch_name="chromeos-kernelupstream-6.2-rc3",
            )
        )
        print("Received BisectKbuildResponse message with:")
        print_msg(rep)

        while True:
            print("Sending BisectKbuildStatusRequest message")
            rep = stub.GetBisectKbuildStatus(
                BisectKbuildStatusRequest(session_id=rep.session_id)
            )
            print("Received BisectKbuildStatusResponse message with:")
            print_msg(rep)
            if (
                rep.error_code == Error.NO_ERROR
                and rep.kbuild_status == Status.COMPLETED
            ):
                break

        print("Sending DutProvisionRequest message")
        rep = stub.ProvisionDut(
            DutProvisionRequest(
                session_id=rep.session_id,
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

        while True:
            print("Sending DutProvisionStatusRequest message")
            rep = stub.GetDutProvisionStatus(
                DutProvisionStatusRequest(session_id=rep.session_id)
            )
            print("Received DutProvisionStatusResponse message with:")
            print_msg(rep)
            if (
                rep.error_code == Error.NO_ERROR
                and rep.provision_status == Status.COMPLETED
            ):
                break


if __name__ == "__main__":
    logging.basicConfig()
    run()
