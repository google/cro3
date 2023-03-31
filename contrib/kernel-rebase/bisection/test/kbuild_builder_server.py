# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=no-name-in-module

"""Server side code for testing the kbuild builder interface"""

from concurrent import futures
import logging

from common import print_msg
import grpc
from kbuild_builder_pb2 import BisectKbuildResponse
from kbuild_builder_pb2 import DutProvisionResponse
from kbuild_builder_pb2 import Status
from kbuild_builder_pb2_grpc import add_KbuildBuilderServicer_to_server
from kbuild_builder_pb2_grpc import KbuildBuilderServicer


class Intf(KbuildBuilderServicer):
    """Implements server side of kbuild builder interface"""

    def CreateBisectKbuild(self, request, context):
        print("Received BisectKbuildRequest message with:")
        print_msg(request)

        print("Sending BisectKbuildResponse message\n")
        return BisectKbuildResponse(
            kbuild_status=Status.COMPLETED,
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
            provision_status=Status.COMPLETED,
            kernel_version="5.10",
        )


def serve():
    """Main server loop"""

    port = "50051"
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    add_KbuildBuilderServicer_to_server(Intf(), server)
    server.add_insecure_port("[::]:" + port)
    server.start()
    print("Server started, listening on " + port)
    server.wait_for_termination()
    print("")


if __name__ == "__main__":
    logging.basicConfig()
    serve()
