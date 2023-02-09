#!/usr/bin/env python3
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""The client side code of corp-ssh-helper-helper.

This script has the same command line interface and functionality as
corp-ssh-helper. To provide the functionality, it forwards the parameters and
standard IO FDs to the server process.
"""

import argparse
import array
import json
import logging
import os
import socket
import sys


_MAX_DATA_SIZE = 4096

_SCRIPT_NAME = os.path.basename(__file__)


def main() -> int:
    """The main function."""
    arg_parser = argparse.ArgumentParser(prog=_SCRIPT_NAME)
    arg_parser.add_argument(
        "-dest4",
        action="store_true",
        help=(
            "Use local DNS resolution to connect from relay to destination "
            "host using IPv4."
        ),
    )
    arg_parser.add_argument(
        "-dest6",
        action="store_true",
        help=(
            "Use local DNS resolution to connect from relay to destination "
            "host using IPv6."
        ),
    )
    arg_parser.add_argument("host")
    arg_parser.add_argument("port")
    args = arg_parser.parse_args()

    path = os.path.expanduser("~/chromiumos/.corp-ssh-helper-helper.sock")
    with socket.socket(socket.AF_UNIX) as s:
        try:
            s.connect(path)
        except (ConnectionRefusedError, FileNotFoundError) as err:
            logging.error(
                "Failed to connect to %s: %s. "
                "Did you start corp-ssh-helper-helper-server?",
                path,
                err,
            )
            return 1

        # Send a request JSON and standard IO FDs of this process to the server.
        # After that, the server will perform all IOs on behalf of this process.
        msg = json.dumps(
            {
                "host": args.host,
                "port": args.port,
                "dest4": args.dest4,
                "dest6": args.dest6,
            }
        ).encode("utf-8")
        fds = [sys.stdin.fileno(), sys.stdout.fileno(), sys.stderr.fileno()]
        s.sendmsg(
            [msg],
            [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array("i", fds))],
        )

        # Close stdin and stdout. This process no longer needs them.
        # NOTE: stderr is still kept open so this process can use it to report
        # unhandled exceptions and for logging.
        os.close(sys.stdin.fileno())
        os.close(sys.stdout.fileno())

        # Wait for a response from the server.
        return json.loads(s.recv(_MAX_DATA_SIZE))["returncode"]


if __name__ == "__main__":
    sys.exit(main())
