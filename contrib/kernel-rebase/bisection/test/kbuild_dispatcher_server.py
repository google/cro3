# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=no-name-in-module

"""Server side code for testing the kbuild dispatcher interface"""

from concurrent import futures
import logging

from common import print_msg
import grpc
from kbuild_dispatcher_pb2 import BisectKbuildResponse
from kbuild_dispatcher_pb2 import BisectKbuildStatusResponse
from kbuild_dispatcher_pb2 import BisectSessionResponse
from kbuild_dispatcher_pb2 import DutProvisionResponse
from kbuild_dispatcher_pb2 import DutProvisionStatusResponse
from kbuild_dispatcher_pb2 import Error
from kbuild_dispatcher_pb2 import Status
from kbuild_dispatcher_pb2_grpc import add_KbuildDispServicer_to_server
from kbuild_dispatcher_pb2_grpc import KbuildDispServicer


class Intf(KbuildDispServicer):
    """Implements server side of kbuild dispatcher interface"""

    kbuild_status_cnt = 0
    update_status_cnt = 0

    def CreateBisectSession(self, request, context):
        print("Received BisectSessionRequest message with:")
        print_msg(request)
        self.kbuild_status_cnt = 0
        self.update_status_cnt = 0
        print("Sending BisectSessionResponse message\n")
        return BisectSessionResponse(
            error_code=Error.NO_ERROR, session_id=request.session_id
        )

    def CreateBisectKbuild(self, request, context):
        print("Received BisectKbuildRequest message with:")
        print_msg(request)
        print("Sending BisectKbuildResponse message\n")
        if request.commit_sha == "ebddb1404900657b7f03a56ee4c34a9d218c4030":
            return BisectKbuildResponse(
                error_code=Error.KBUILD_ALREADY_EXISTS,
                session_id=request.session_id,
                kbuild_archive_path=(
                    "gs://kcr-bisection/volteer-kernelnext_chromeos-"
                    "kernelupstream-6.2-rc3_"
                    "ebddb1404900657b7f03a56ee4c34a9d218c4030.tgz"
                ),
            )

        return BisectKbuildResponse(
            error_code=Error.NO_ERROR, session_id=request.session_id
        )

    def GetBisectKbuildStatus(self, request, context):
        print("Received BisectKbuildStatusRequest message with:")
        print_msg(request)

        self.kbuild_status_cnt = self.kbuild_status_cnt + 1
        print("Sending BisectKbuildStatusResponse message\n")
        if self.kbuild_status_cnt > 1:
            return BisectKbuildStatusResponse(
                error_code=Error.NO_ERROR,
                kbuild_status=Status.IN_PROGRESS,
                session_id=request.session_id,
                kbuild_archive_path=(
                    "gs://kcr-bisection/volteer-kernelnext_chromeos-"
                    "kernelupstream-6.2-rc3_"
                    "d1678bf45f21fa5ae4a456f821858679556ea5f8.tgz"
                ),
            )

        return BisectKbuildStatusResponse(
            error_code=Error.NO_ERROR,
            kbuild_status=Status.COMPLETED,
            session_id=request.session_id,
            kbuild_archive_path=(
                "gs://kcr-bisection/volteer-kernelnext_chromeos-"
                "kernelupstream-6.2-rc3_"
                "d1678bf45f21fa5ae4a456f821858679556ea5f8.tgz"
            ),
        )

    def ProvisionDut(self, request, context):
        print("Received DutProvisionRequest message with:")
        print_msg(request)
        print("Sending DutProvisionResponse message\n")
        return DutProvisionResponse(
            error_code=Error.NO_ERROR, session_id=request.session_id
        )

    def GetDutProvisionStatus(self, request, context):
        print("Received DutProvisionStatusRequest message with:")
        print_msg(request)

        self.update_status_cnt = self.update_status_cnt + 1
        if self.update_status_cnt > 1:
            return DutProvisionStatusResponse(
                error_code=Error.NO_ERROR,
                provision_status=Status.COMPLETED,
                session_id=request.session_id,
                kernel_version="5.10",
            )
        print("Sending DutProvisionStatusResponse message\n")
        return DutProvisionStatusResponse(
            error_code=Error.NO_ERROR,
            provision_status=Status.IN_PROGRESS,
            session_id=request.session_id,
        )


def serve():
    """Main server loop"""

    port = "50051"
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_KbuildDispServicer_to_server(Intf(), server)
    server.add_insecure_port("[::]:" + port)
    server.start()
    print("Server started, listening on " + port)
    server.wait_for_termination()
    print("")


if __name__ == "__main__":
    logging.basicConfig()
    serve()
