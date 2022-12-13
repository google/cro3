#!/usr/bin/env python3

# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""
Note: This grpc service is a short term solution that will be deprecated
once the CTRv2 is complete
"""

from concurrent import futures
import subprocess
import os
import logging
import grpc
import pathlib
import sys


# Used to import the proto stack
if "CONFIG_REPO_ROOT" in os.environ:
    sys.path.insert(1, os.path.join(os.getenv("CONFIG_REPO_ROOT"), "python"))
else:
    sys.path.insert(1, str(pathlib.Path(__file__).parent.resolve() /
                    '../../../../../../../../config/python'))

import chromiumos.test.api.cros_test_runner_service_pb2 as cros_test_runner_service_pb2
import chromiumos.test.api.cros_test_runner_service_pb2_grpc as cros_test_runner_service_pb2_grpc


class CrosTestRunnerService(cros_test_runner_service_pb2_grpc.CrosTestRunnerServiceServicer):
    """A grpc service that runs tests via the run_cros_test cli"""

    def Run(self, request, _):
        run_cros_test_path = str(pathlib.Path(
            __file__).parent.resolve() / './run_cros_test.py')
        output_dir = os.environ["CROS_TEST_OUTPUT_DIR"]
        results_dir = os.path.join(output_dir, "results", request.results_dir_name)

        cft_run_cmd = [
            run_cros_test_path,
            f"-host={request.host}",
            f"-board={request.board}",
            f"-tests={','.join(request.tests)}",
            f"-results={results_dir}",
            f"-image={request.cros_test_image_tag}"
        ]
        if len(request.autotest_args) != 0:
            cft_run_cmd.append(
                f"-autotest_args={self.__autotest_args_to_str(request.autotest_args)}",)

        logging.info(f"running tests with command: `{' '.join(cft_run_cmd)}`")
        run = subprocess.run(cft_run_cmd, capture_output=True)
        return cros_test_runner_service_pb2.RunCrosTestResponse(stdout=run.stdout, stderr=run.stderr, return_code=run.returncode)

    def __autotest_args_to_str(self, autotest_args):
        flag_value_pairs = [
            f"{autotest_arg.flag}={autotest_arg.value}" for autotest_arg in autotest_args]
        return " ".join(flag_value_pairs)


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    cros_test_runner_service_pb2_grpc.add_CrosTestRunnerServiceServicer_to_server(
        CrosTestRunnerService(), server)
    server.add_insecure_port('[::]:50051')

    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    serve()
