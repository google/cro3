#!/usr/bin/env python3
# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""The server side code of corp-ssh-helper-helper.

The server process waits for connection requests from client processes.
When receiving a request, it runs corp-ssh-helper to perform network IO on
behalf of the client.
"""

import argparse
import array
import json
import logging
import os
import re
import socket
import subprocess
import sys
import threading
from typing import Any, Dict, Optional, Sequence


_MAX_DATA_SIZE = 4096

_SCRIPT_NAME = os.path.basename(__file__)


def _find_chromiumos_checkout_root(path: str) -> Optional[str]:
    """Returns the ChromiumOS checkout root path.

    Returns the checkout root path if the given path belongs to a ChromiumOS
    checkout. Otherwise returns None.
    """

    # Give up and return None when reaching the file system root.
    if path == '/':
        return None

    # Try to find some known subdirectories under the checkout root.
    is_chromiumos_checkout_root = True
    for child_name in ['chroot', 'chromite', 'src']:
        child_path = os.path.join(path, child_name)
        if not os.path.exists(child_path):
            is_chromiumos_checkout_root = False

    if is_chromiumos_checkout_root:
        # This is the checkout root. Return the path.
        return path

    # This doesn't look like a checkout root. Move one level up and retry.
    return _find_chromiumos_checkout_root(os.path.dirname(path))


def _daemonize() -> None:
    """Starts running as a background process.

    This function uses the well known double fork technique to keep running the
    process even after the original process exits.
    """

    # First fork.
    if os.fork():
        # Exit the original process.
        sys.exit(0)

    # The first forked process starts its own session.
    os.setsid()

    # Second fork.
    if os.fork():
        # Exit the first forked process.
        sys.exit(0)

    # Override standard IO with /dev/null and continue running the second forked
    # process.
    with open(os.devnull, 'r+') as f:
        os.dup2(f.fileno(), sys.stdin.fileno())
        os.dup2(f.fileno(), sys.stdout.fileno())
        os.dup2(f.fileno(), sys.stderr.fileno())


def _handle_request(conn: socket.socket,
                    msg: Dict[str, Any],
                    fds: Sequence[int]) -> None:
    """Handles an incoming connection request from a client."""
    with conn:
        # Run corp-ssh-helper with the passed parameters.
        with os.fdopen(fds[0], 'rb') as stdin, os.fdopen(
            fds[1], 'wb') as stdout, os.fdopen(fds[2], 'wb') as stderr:

            # Check if the given host name is a valid IPv4 address, IPv6
            # address, or a host name which satisfies the spec described in
            # `man hosts`.
            host = msg['host']
            if (not re.match(r'^[0-9.]+$', host) and  # IPv4 address
                not re.match(r'^[0-9a-fA-F:]+$', host) and  # IPv6 address
                not re.match(r'^[A-Za-z][A-Za-z0-9-.]*$', host)):  # host name
                raise RuntimeError(f'"{host}" is not a valid host name')

            port = msg['port']
            if not re.match(r'^\d+$', port):
                raise RuntimeError(f'"{port}" is not a valid port number')

            args = ['corp-ssh-helper']
            if msg['dest4']:
                args.append('-dest4')
            if msg['dest6']:
                args.append('-dest6')
            args.append(host)
            args.append(port)

            logging.info('Connecting to %s:%s. proxycommand="%s"', host, port,
                         ' '.join(args))
            returncode = subprocess.run(args, stdin=stdin, stdout=stdout,
                                        stderr=stderr, check=False).returncode

            # After the proxy command exits, send a response JSON to the client.
            conn.send(json.dumps({'returncode': returncode}).encode('utf-8'))


def main() -> int:
    """The main function."""
    logging.basicConfig(level=logging.INFO)

    # The named UNIX domain socket created by this process should be used only
    # by the same user.
    os.umask(0o077)

    arg_parser = argparse.ArgumentParser(prog=_SCRIPT_NAME)
    arg_parser.add_argument(
        '--foreground', action='store_true', help='Run in the foreground')
    arg_parser.add_argument(
        '--kill', action='store_true', help='Kill the existing server process')
    args = arg_parser.parse_args()

    # Try to find the checkout root from the current directory's ancestors.
    chromeos_path = _find_chromiumos_checkout_root(os.getcwd())
    if not chromeos_path:
        logging.error('Please run this script under a ChromiumOS checkout.')
        return 1

    socket_path = os.path.join(chromeos_path, '.corp-ssh-helper-helper.sock')

    if os.path.exists(socket_path):
        # Try connecting to the existing socket to check if there is an existing
        # server process.
        with socket.socket(socket.AF_UNIX) as s:
            try:
                s.connect(socket_path)
            except ConnectionRefusedError as err:
                # ConnectionRefusedError means there is no existing server
                # process.
                if args.kill:
                    logging.error('--kill was specified, but there is no '
                                  'existing process to kill.')
                    return 1

                # Delete the existing socket and continue.
                os.remove(socket_path)
            else:
                # If connect() doesn't raise an exception, that means there is a
                # running server process.
                if args.kill:
                    # Send a kill request to the existing server process.
                    msg_bytes = json.dumps({'kill': True}).encode('utf-8')
                    s.sendmsg([msg_bytes])
                    logging.info('Sent a kill request to the existing server '
                                 'process.')
                    return 0

                logging.error('The server is already running. If you want '
                              'to stop it, please use --kill.')
                return 1


    # Start listening on the socket.
    with socket.socket(socket.AF_UNIX) as s:
        s.bind(socket_path)
        s.listen()
        logging.info('Listening on %s', socket_path)

        # After this, run in the background unless running with --foreground.
        if not args.foreground:
            _daemonize()

        # The main loop of this server process.
        while True:
            # Wait for a client connection.
            conn, _ = s.accept()

            # Receive the request message and standard IO FDs.
            fds = array.array('i')
            msg_bytes, ancdata, _, _ = conn.recvmsg(
                _MAX_DATA_SIZE, socket.CMSG_LEN(3 * fds.itemsize))
            for cmsg_level, cmsg_type, cmsg_data in ancdata:
                if (cmsg_level == socket.SOL_SOCKET and
                    cmsg_type == socket.SCM_RIGHTS):
                    fds.frombytes(cmsg_data[:len(cmsg_data) -
                                            (len(cmsg_data) % fds.itemsize)])

            # Interpret the message as a JSON.
            try:
                msg = json.loads(msg_bytes)

                # When receiving a kill request, just exit.
                if msg.get('kill'):
                    logging.info('Received a kill request. Going to exit.')
                    return 0

                # Start a new thread to handle the connection request.
                threading.Thread(
                    target=_handle_request, args=(conn, msg, fds)).start()

            except json.decoder.JSONDecodeError as err:
                logging.error('Invalid message from the client: %s', err)


if __name__ == '__main__':
    sys.exit(main())
