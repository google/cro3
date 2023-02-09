#!/usr/bin/env python3
# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Entry point for Local CFT execution.

This script will use cros-tool-runner for execution.
"""


import argparse
import json
import os
import pathlib
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from typing import Tuple


sys.path.insert(1, str(pathlib.Path(__file__).parent.resolve() / "../../"))

from src.common.utils import (
    run,  # pylint: disable=import-error,wrong-import-position
)
from src.tools.container_updater import ContainerUpdater
from src.tools.proto_templates import make_prov_request
from src.tools.proto_templates import make_testFinderRequest
from src.tools.proto_templates import make_testRequest


def parse_local_arguments() -> argparse.Namespace:
    """Parse the CLI."""
    parser = argparse.ArgumentParser(
        description="Prep Tauto, Tast, & Services for DockerBuild."
    )
    parser.add_argument(
        "--chroot",
        dest="chroot",
        default="foo",
        help="chroot (String): The chroot path to use.",
    )
    parser.add_argument(
        "-results",
        dest="results",
        default=("/tmp/results/CFTtest/"),
        help="Results volume on local fs",
    )
    parser.add_argument(
        "-tests",
        dest="tests",
        nargs="*",
        default=None,
        help='test(s) to run. Example: "-tests test1 test2"',
    )
    parser.add_argument(
        "-tags",
        dest="tags",
        nargs="*",
        default=None,
        help="tags(s) to run. Example usage: " '"-tests suite:1 suite:2"',
    )
    parser.add_argument(
        "-host", dest="host", default=None, help="hostname of dut."
    )
    parser.add_argument(
        "-dutport",
        dest="dutport",
        default=None,
        type=int,
        help="hostname of dut.",
    )
    parser.add_argument("-board", dest="board", default=None, help="Board name")
    parser.add_argument("-model", dest="model", default=None, help="Model name")
    parser.add_argument(
        "-build",
        dest="build",
        default="",
        help="Build number to run containers from."
        " Eg R108 or R108-14143. Do not use with -md_path",
    )
    parser.add_argument(
        "-md_path",
        dest="md_path",
        default=None,
        help="Path containing the container metadata. Not to be "
        " used with -build",
    )
    parser.add_argument(
        "--fullrun",
        action="store_true",
        help='Use if you want a full "e2e" run',
    )
    parser.add_argument(
        "--provision",
        action="store_true",
        help="Addative flag. Set if you want to provision.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Addative flag. Set if you want to test.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Addative flag. Set if you want to publish "
        "results. Must have test set to -test set True",
    )
    parser.add_argument(
        "-image_path",
        dest="image_path",
        help="image path to use for image artifacts.",
    )
    parser.add_argument(
        "--update_containers",
        action="store_true",
        help="update the containers defined in the given "
        "(or discovered) metadata.",
    )
    parser.add_argument(
        "-chroot_path",
        dest="chroot_path",
        help="path to chroot, required if --update_containers",
    )
    parser.add_argument(
        "-sysroot_path",
        dest="sysroot_path",
        help="path to sysroot, required if --update_containers,"
        " and updating a test container.",
    )
    parser.add_argument(
        "-service_updates",
        dest="service_updates",
        nargs="*",
        help="binary/services to update. Example: "
        '"-service_updates cros-test cros-dut"',
    )
    parser.add_argument(
        "-rtd_updates",
        dest="rtd_updates",
        nargs="*",
        help="RTDs to update. Note: This is slow and heavy, only"
        ' use if reqd. Example: "-rtd_updates tauto tast"',
    )
    # Not implemented yet. Autotunnels will be required for the first iteration
    # due to the complexity with getting the reverse tunnel w/ cros-dut and
    # cacheserver setup.
    # parser.add_argument('--no_auto_tunnel',
    #                     action='store_true',
    #                     help='Automatically setup all the SSH tunnels. NOTE: '
    #                          'This will run a `reset` on the shell after '
    #                          'building the tunnels due the subprocess leaking '
    #                          'control codes into the terminal. If you do not '
    #                          'want the `reset` run, then set this flag and '
    #                          'manually create the tunnels and pass in the '
    #                          'ports via the TBD flags')

    # Not implemented as the registry is going to store containers for ~ 10 days.
    # Maybe will increase release builds to be stored for longer.
    # parser.add_argument('--use_prebuilts',
    #                     dest='use_prebuilts',
    #                     action='store_true',
    #                     help='If set, will download pre-built CFT containers '
    #                           'based off DUT image')

    args = parser.parse_args()
    return args


def find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))  # Bind to a free port provided by the host.
        return s.getsockname()[1]  # Return the port number assigned.


def docker_installed() -> bool:
    if run("docker", stream=False)[2] != 0:
        return False
    return True


def download_metadata(args: argparse.Namespace) -> Tuple[str, str]:
    """Download the container metadata, and return paths."""
    template = (
        f"gs://chromeos-image-archive/{args.board}-release/"
        f"{args.build}*/metadata/containers.jsonpb"
    )

    # Cast a "wide" net on the build, so that partial build numbers can be found.
    out, err, code = run(f"gsutil ls -l {template} | sort -k 2", stream=False)
    if out and code == 0:
        # Get the last (newest) build specified.
        archive_path = out.split("gs://")[-1]
        # there is extra stdout fluff, strip it off.
        archive_path = f'{archive_path.split(".jsonpb")[0]}.jsonpb'
        if "metadata/containers.jsonpb" not in archive_path:
            raise Exception("Path did not have metadata")

        # Note the image path we fetch from for later use.
        image_path = archive_path.split("metadata")[0]

        run(f"gsutil cp gs://{archive_path} .")
        if not os.path.isfile("containers.jsonpb"):
            raise Exception("Downloaded file missing")
        return "containers.jsonpb", f"gs://{image_path}"
    raise Exception(f"Could not download metadata. {err}")


def validate_args(args: argparse.Namespace):
    if not args.model or not args.board:
        raise Exception("-model and -board must be provided!")
    # Remove once publish is set.
    if args.publish:
        raise NotImplementedError("Publish not implemented for local CFT.")
    if args.tests and not isinstance(args.tests, list):
        raise Exception("Tests must be given as a list.")
    if args.tags and not isinstance(args.tags, list):
        raise Exception("Tags must be given as a list.")
    if args.md_path and args.provision and not args.image_path:
        raise Exception(
            "image_path must be given if provisioning w/" " custom metadata."
        )
    if args.build and args.md_path:
        raise Exception(
            "-build and -md_path are exclusive (do not use togther)."
        )
    if not args.md_path and not args.build:
        raise Exception(
            "One of -build or -md_path must be included"
            " such that the metadata can be found."
        )
    if args.update_containers:
        validate_update_args(args)


def validate_update_args(args: argparse.Namespace):
    """Specifically validate the args around the container updating."""
    if args.rtd_updates and not args.sysroot_path:
        raise Exception("sysroot_path must be given when updating RTDs.")
    if not args.rtd_updates and not args.service_updates:
        raise Exception(
            "either -rtd_updates or -service_updates must be set when "
            "--update_containers is set."
        )
    if not args.chroot_path:
        raise Exception("chroot_path must be given when updating containers.")


def validate_prereqs():
    """Validate required binaries are installed."""
    if not run("which docker")[0]:
        print('"Docker" must be installed prior to use.')
        sys.exit(1)
    if not run("which autossh")[0]:
        print('"autossh" must be installed prior to use.')
        sys.exit(1)

    proc = subprocess.Popen(
        "gcloud artifacts docker images list "
        "us-docker.pkg.dev/cros-registry/test-services/cros-test --limit 1",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
    )
    _, stderr = proc.communicate()
    if proc.returncode == 1 and "invalid_grant: Bad Request" in stderr.decode():
        print(
            "Docker not authd. Please run: \n"
            "\tgcloud auth configure-docker us-docker.pkg.dev\nThen try again."
        )
        sys.exit(1)


def make_ssh_cmd(cmd: str) -> str:
    """Return the autossh command."""
    base = (
        'autossh -M 0 -o "ServerAliveInterval 5" -o "ServerAliveCountMax 2"'
        ' -o "UserKnownHostsFile=/dev/null"  -o "StrictHostKeyChecking=no" '
    )
    return base + cmd + " -N"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


class ProxyManager(object):
    """Manager of proxy/tunnels to the DUT/services."""

    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.tunnel_file = None
        self.tunnel_port = None
        self.tunnel_process = None
        self.reverse_tunnel_file = None
        self.reverse_tunnel_port = None
        self.reverse_tunnel_process = None
        self.cache_port = None
        self.cache_file = None
        self.cache_process = None

    def setup_dut_tunnel(self):
        """Establishes an autossh tunnel to the DUT."""
        self.tunnel_port = self.args.dutport
        if not self.tunnel_port:
            self.tunnel_port = find_free_port()

        cmd = make_ssh_cmd(
            f"-L {self.tunnel_port}:localhost:22 root@{self.args.host}"
        )
        self.tunnel_file = open("norm_tunnel", "w")
        self.tunnel_process = subprocess.Popen(
            cmd, shell=True, stdout=self.tunnel_file, stderr=self.tunnel_file
        )

    def setup_dut_reverse_tunnel(self):
        """Establishes an autossh reverse tunnel to the DUT/cacheserver."""
        rev_port = find_free_port()
        cache_port = find_free_port()
        if rev_port == cache_port:
            # TODO, these are randomly generated, but technically
            # since we do not bind until after finding a free port,
            # we could clash.
            raise Exception("Port clash for rev")

        cmd = make_ssh_cmd(
            f"-R {rev_port}:localhost:{cache_port} root@{self.args.host} -p 22"
        )
        self.reverse_tunnel_port = rev_port
        self.cache_port = cache_port
        self.reverse_tunnel_file = open("rev_tunnel", "w")
        self.reverse_tunnel_process = subprocess.Popen(
            cmd,
            shell=True,
            stdout=self.reverse_tunnel_file,
            stderr=self.reverse_tunnel_file,
        )

    def setup_ports(self):
        """Establish all ports requires for testing."""
        self.setup_dut_tunnel()
        self.setup_dut_reverse_tunnel()
        if not self.wait_for_port(self.tunnel_port):
            print(
                "DUT Tunnel not found!. Please ensure:\n"
                "1.) gcert has been run\n"
                "2.) The SSH config has the public ssh key for the DUT."
            )
            self.cleanup_ports()
            sys.exit(1)

        self.startCacheServer()
        if not self.wait_for_port(self.cache_port):
            print("Cache Tunnel port failed to start.")
            self.cleanup_ports()
            sys.exit(1)

    def startCacheServer(self):
        """Run the cacheserver from a static docker image."""
        port = self.cache_port
        cmd = (
            "docker run --network host -v ~/.config/:/root/.config "
            "us-docker.pkg.dev/cros-registry/test-services/cros-test:cache-server"
            " cacheserver -location /tmp/cacheserver -port "
            f"{port}"
        )

        self.cache_file = open("cacheout", "w")
        self.cache_process = subprocess.Popen(
            cmd, shell=True, stdout=self.cache_file, stderr=self.cache_file
        )

    def cleanup_ports(self):
        """Cleanup all open ports, closing log files and autossh pids."""
        # Using the "is not None" in case the process is "empty"
        # and "is" evals False for some reason... still try to kill/close.
        if self.tunnel_process is not None:
            os.kill(self.tunnel_process.pid, signal.SIGTERM)
        if self.tunnel_file:
            self.tunnel_file.close()
        if self.reverse_tunnel_process is not None:
            os.kill(self.reverse_tunnel_process.pid, signal.SIGTERM)
        if self.reverse_tunnel_file:
            self.reverse_tunnel_file.close()
        if self.cache_process is not None:
            os.kill(self.cache_process.pid, signal.SIGTERM)
        if self.cache_file:
            self.cache_file.close()

    def wait_for_port(self, port: int) -> bool:
        """Wait for the port to be up."""
        st = time.time()
        while time.time() - st < 25:
            if is_port_in_use(port):
                return True
            time.sleep(0.25)
        return False


class CTRRunner(object):
    """The Cros-tool-runner, runner."""

    def __init__(self, args: argparse.Namespace, md_path: str, image_path: str):
        self.args = args
        self.ProxyManager = None
        self.resultsDir = ""
        self.cache_file = None
        self.cache_process = None
        self.image_path = image_path
        self.md_path = md_path
        self.ctf_tests = {}

        self.startup()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        """Exit for context libs. Forces cleanup on proxymanager."""
        if self.ProxyManager:
            self.ProxyManager.cleanup_ports()

    def startup(self):
        """Setup for testing

        Download CTR if it does not exist, setup tunnels and cacheserver.
        """
        if not self.ctr_exists():
            self.download_ctr()
        # Startups the proxys/tunnels
        self.ProxyManager = ProxyManager(self.args)
        self.ProxyManager.setup_ports()
        print("Tunnel setup completed")
        self.setup_artifactsDir()

    def ctr_exists(self) -> bool:
        if os.path.isfile("cros-tool-runner"):
            print("cros-tool-runner found.")
            return True
        return False

    def chromeOS_Provision(self):
        """Provision the DUT with specified chromeOS version."""
        self.write_request_proto_to_file(self.make_prov_req_proto())
        cmd = self.ctr_cmd(service="provision")
        run(cmd)

    def find_test(self):
        """Find test(s) using CFT (cros-test-finder)."""
        proto = self.make_test_finder_req_proto()
        self.write_request_proto_to_file(proto)
        cmd = self.ctr_cmd(service="test-finder")
        run(cmd)
        self.convertCTFOut()

    def convertCTFOut(self):
        """Convert the test-finder output from testcases --> testcaseIds."""
        with open("cros-test-finder/result.json", "r") as rf:
            testjson = json.load(rf)

        suites = testjson["testSuites"]
        alltests = []
        for testgroup in suites:
            for test in testgroup["testCases"]["testCases"]:
                alltests.append({"value": test["id"]["value"]})

        self.ctf_tests = {"testCaseIds": {"testCaseIds": alltests}}

    def run_test(self):
        """Run a test using cft"""
        self.write_request_proto_to_file(self.make_test_req_proto())
        run(self.ctr_cmd(service="test"))

    def download_ctr(self):
        """Download the latest CTR CIPD package."""
        run(
            "wget https://chrome-infra-packages.appspot.com/dl/chromiumos/"
            "infra/cros-tool-runner/linux-amd64/+/latest"
        )
        run("unzip latest -d .")
        run("rm -r latest")

    def make_test_req_proto(self) -> dict:
        return make_testRequest(
            artifactDir=self.resultsDir,
            board_key=self.args.board,
            cacheIp="localhost",
            cachePort=self.ProxyManager.reverse_tunnel_port,
            model_key=self.args.model,
            sshAddr="localhost",
            port=self.ProxyManager.tunnel_port,
            tests=self.ctf_tests,
        )

    def make_test_finder_req_proto(self) -> dict:
        return make_testFinderRequest(
            board_key=self.args.board,
            tests=self.args.tests,
            tags=self.args.tags,
        )

    def make_prov_req_proto(self) -> dict:
        return make_prov_request(
            board_key=self.args.board,
            cacheIp="localhost",
            cachePort=self.ProxyManager.reverse_tunnel_port,
            model_key=self.args.model,
            sshAddr="localhost",
            port=self.ProxyManager.tunnel_port,
            image_src=self.image_path,
        )

    def ctr_cmd(
        self, service: str, docker_keyfile: str = "", req_path: str = "req.json"
    ) -> str:
        cmd = f"./cros-tool-runner {service} "
        if docker_keyfile:
            cmd += f"-docker_key_file {docker_keyfile} "
        cmd += f"-images {self.md_path} "
        cmd += f"-input {req_path} "
        cmd += "-output /dev/stdout "
        return cmd

    def setup_artifactsDir(self):
        """Build an artifact directory for CFT results."""
        if os.path.isdir(self.args.results):
            try:
                print(
                    f"WARNING: Removing Prior results dir {self.args.results}"
                )
                # This can't delete results from a previous test because of
                # the permissions on some of the files made by CFT requiring sudo
                # to delete. Need to figure this one out...
                shutil.rmtree(self.args.results)
                resultsDir = self.args.results
                pathlib.Path(resultsDir).mkdir(parents=True)
            except OSError:
                prefix = os.path.dirname(self.args.results) + "/"
                resultsDir = tempfile.mkdtemp(prefix=prefix)
                print(f"Could not delete results dir. Will use: {resultsDir}")
        else:
            resultsDir = self.args.results
            print(f"Making path {resultsDir}")
            run(f"mkdir -p {resultsDir}")

        run(f"chmod 777 -R {resultsDir}")
        self.resultsDir = os.path.join(resultsDir, "cros-tool-runner")
        pathlib.Path(self.resultsDir).mkdir(parents=True)

    def write_request_proto_to_file(self, req: dict):
        with open("req.json", "w") as fp:
            json.dump(req, fp)


def _should_update_rtd(rtd, args):
    return args.rtd_updates and rtd in args.rtd_updates


def main():
    """Entry point."""
    args = parse_local_arguments()
    validate_args(args)
    validate_prereqs()
    if not args.md_path:
        md_path, image_path = download_metadata(args)
    else:
        md_path = args.md_path
        image_path = args.image_path

    if args.update_containers:
        md_path = ContainerUpdater(
            metadata=md_path,
            services=args.service_updates,
            tast=_should_update_rtd("tast", args),
            autotest=_should_update_rtd("tauto", args),
            chroot=args.chroot_path,
            sysroot=args.sysroot_path,
            board=args.board,
        ).Update_Containers()
    with CTRRunner(args, md_path, image_path) as ctrRunner:
        cmds = []
        if args.fullrun:
            cmds.extend(
                [
                    ctrRunner.chromeOS_Provision,
                    ctrRunner.find_test,
                    ctrRunner.run_test,
                ]
            )
        if args.provision:
            cmds.append(ctrRunner.chromeOS_Provision)
        if args.test:
            cmds.extend([ctrRunner.find_test, ctrRunner.run_test])
        if args.publish:
            pass
        for cmd in cmds:
            cmd()


if __name__ == "__main__":
    main()
