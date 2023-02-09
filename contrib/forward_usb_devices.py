#!/usr/bin/env python3
# Copyright 2020 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Forward USB devices from the caller to the target device.

Automates the process of forwarding specified USB devices to a target device.
This involves:

  1) Loading the prerequisite kernel modules (both locally and on the target
     device).
  2) Running and cleaning up `usbipd`.
  3) Setting up a SSH tunnel for the `usbipd` TCP port.
  4) Bind the devices to the usbip kernel driver.
  5) Attach the devices to the target.
  6) Clean up on exit so that the USB devices will function again locally.

For example:
  ./forward_usb_devices.py --log-level=debug -d test-device.local 1-3.1 1-3.2
will forward two USB devices (the ones at bus ids 1-3.1 and 1-3.2) to the device
with the hostname `test-device.local`.

Requires usbip installed in the chroot:

(chroot) $ sudo emerge usbip

To list USB bus ids:

(chroot) $ usbip list --local


"""

from __future__ import print_function

import contextlib
import logging
import os
import shutil
import signal
import subprocess
import sys
import time

from chromite.lib import commandline
from chromite.lib import cros_build_lib
from chromite.lib import osutils
from chromite.lib import remote_access
from chromite.lib import retry_util


HOST_MODULES = {"usbip-core", "usbip-host", "vhci-hcd"}
CLIENT_MODULES = {"usbip-core", "vhci-hcd"}

KILL_COMMAND = "kill"

MODPROBE_COMMAND = "modprobe"

USBIP_PACKAGE = "usbip"
USBIP_COMMAND = "usbip"
USBIPD_COMMAND = "usbipd"
USBIPD_PID_FILE = "/run/usbipd.pid"
USBIPD_PORT = 3240

RETRY_USBIPD_READ_PID = 10
DELAY_USBIPD_READ_PID = 0.5


def main(argv):
    """Forward USB devices from the caller to the target device."""
    os.environ["PATH"] += ":/sbin:/usr/sbin"

    opts = get_opts(argv)
    return forward_devices(
        opts.device.hostname, opts.device.port, opts.usb_devices
    )


def forward_devices(hostname, port, usb_devices):
    """Forward USB devices from the caller to the target device."""

    if shutil.which(USBIP_COMMAND) is not None:
        logging.debug("`%s` found in the chroot", USBIP_COMMAND)
    else:
        logging.error(
            "You need to emerge the `%s` package in the chroot: sudo emerge %s",
            USBIP_PACKAGE,
            USBIP_PACKAGE,
        )

    logging.debug("Connecting to root@%s:%s`", hostname, port)
    with contextlib.ExitStack() as stack:
        device = stack.enter_context(
            remote_access.ChromiumOSDeviceHandler(
                hostname=hostname, port=port, username="root"
            )
        )
        if device.HasProgramInPath(USBIP_COMMAND):
            logging.debug("`%s` found on the device", USBIP_COMMAND)
        else:
            logging.error(
                "You need to emerge and deploy the `%s` package to the test "
                "device: emerge-${{BOARD}} %s && cros deploy "
                "--board=${{BOARD}} %s",
                USBIP_PACKAGE,
                USBIP_PACKAGE,
                USBIP_PACKAGE,
            )
            return False

        tunnel_is_alive = stack.enter_context(setup_usbip_tunnel(device))

        if not load_modules(device=device):
            return False

        if not stack.enter_context(start_usbipd()):
            return False

        for busid in usb_devices:
            if not stack.enter_context(bind_usb_device(busid)):
                return False

        if not tunnel_is_alive():
            logging.error("SSH tunnel is dead. Aborting.")
            return False

        for i, busid in enumerate(usb_devices):
            if not stack.enter_context(attach_usb_device(device, busid, i)):
                return False

        # Catch SIGINT, SIGTERM, and SIGHUP.
        try:
            signal.signal(signal.SIGINT, signal.default_int_handler)
            signal.signal(signal.SIGTERM, signal.default_int_handler)
            signal.signal(signal.SIGHUP, signal.default_int_handler)
            logging.info("Ready. Press Ctrl-C (SIGINT) to cleanup.")
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            pass

    logging.debug("Cleanup complete.")
    return True


def get_opts(argv):
    """Parse the command-line options."""
    parser = commandline.ArgumentParser(description=forward_devices.__doc__)
    parser.add_argument(
        "-d",
        "--device",
        type=commandline.DeviceParser(commandline.DEVICE_SCHEME_SSH),
        help="The target device to forward the USB devices to "
        "(hostname[:port]).",
    )
    parser.add_argument(
        "usb_devices",
        nargs="+",
        help="Bus identifiers of USB devices to forward",
    )
    opts = parser.parse_args(argv)
    opts.Freeze()
    return opts


def load_modules(device=None):
    """Load prerequisite kernel modules.

    The modules will first be loaded on the calling machine. If device is set,
    the prerequisite kernel for the target device will also be loaded.
    """
    for module in HOST_MODULES:
        try:
            cros_build_lib.sudo_run([MODPROBE_COMMAND, module])
        except cros_build_lib.RunCommandError:
            logging.error("Failed to load module on host: %s", module)
            return False
        logging.debug("Loaded module on host: %s", module)

    if device is not None:
        for module in CLIENT_MODULES:
            try:
                device.run([MODPROBE_COMMAND, module])
            except cros_build_lib.RunCommandError:
                logging.error("Failed to load module on target: %s", module)
                return False
            logging.debug("Loaded module on target: %s", module)
    return True


@contextlib.contextmanager
def start_usbipd():
    """Starts the `usbipd` daemon in the background.

    On cleanup kills the daemon.

    Returns:
        False on failure.
    """
    try:
        cros_build_lib.sudo_run(
            [USBIPD_COMMAND, "-D", "-P%s" % USBIPD_PID_FILE]
        )
    except cros_build_lib.RunCommandError:
        logging.error("Failed to start: %s", USBIPD_COMMAND)
        yield False
        return
    logging.debug("Started on host: %s", USBIPD_COMMAND)

    # Give the daemon a chance to write the PID file.
    pid = retry_util.GenericRetry(
        handler=lambda e: isinstance(e, FileNotFoundError),
        max_retry=RETRY_USBIPD_READ_PID,
        functor=lambda: int(osutils.ReadFile(USBIPD_PID_FILE).strip()),
        sleep=DELAY_USBIPD_READ_PID,
    )

    yield True

    logging.debug("Killing `usbipd` (%d).", pid)
    cros_build_lib.sudo_run([KILL_COMMAND, str(pid)])


@contextlib.contextmanager
def setup_usbip_tunnel(device):
    """Tunnels the `usbip` port over SSH to the target device.

    On cleanup tears down the tunnel by killing the tunnel process.

    Returns:
        A callback to check if the tunnel is still alive.
    """
    proc = device.GetAgent().CreateTunnel(
        to_remote=[remote_access.PortForwardSpec(local_port=USBIPD_PORT)]
    )

    def alive():
        """Returns `True` if the SSH tunnel process is still alive."""
        return proc.poll() is None

    yield alive

    logging.debug("Stopping `usbip` tunnel.")
    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


@contextlib.contextmanager
def bind_usb_device(busid):
    """Binds the USB device at `busid` to usbip driver so it can be exported.

    On cleanup unbinds the usb device.

    Returns:
        False on failure.
    """
    try:
        cros_build_lib.sudo_run([USBIP_COMMAND, "bind", "-b", busid])
    except cros_build_lib.RunCommandError:
        logging.error("Failed to bind: %s", busid)
        yield False
        return
    logging.debug("Bound: %s", busid)

    yield True

    logging.debug("unbinding: %s", busid)
    cros_build_lib.sudo_run([USBIP_COMMAND, "unbind", "-b", busid])


@contextlib.contextmanager
def attach_usb_device(device, busid, port):
    """Attaches the specified busid using `usbip`.

    On cleanup detaches the USB device at the specified `usbip` port number.

    Returns:
        False on failure.
    """
    try:
        device.run([USBIP_COMMAND, "attach", "-r", "localhost", "-b", busid])
    except cros_build_lib.RunCommandError:
        logging.error("Failed to attach: %s", busid)
        yield False
        return
    logging.debug("Attached: %s", busid)

    yield True

    try:
        device.run([USBIP_COMMAND, "detach", "-p", str(port)])
        logging.debug("Detached usbip port: %s", port)
    except cros_build_lib.RunCommandError:
        logging.error("Failed to detach: %s", port)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
