# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for querying general callbox information."""

from enum import Enum

from acts.controllers import abstract_inst


class CallboxType(Enum):
    """Callbox hardware type."""

    CMX500 = "CMX"
    CMW500 = "CMW"


# Maps callbox type names to type values.
KNOWN_CALLBOXES = {cb.value for cb in CallboxType}


def get_callbox_type(host, port):
    """Attempts to fetch the callbox type by sending a SCIPI command.

    Args:
        host: the callbox hostname or ip.
        port: the callbox port to connect to.

    Returns:
        callbox: a string indicating the callbox type.
            e.x:
                CMW, CMX
    """
    with _SCPIDevice(host, port) as inst:
        type_id = inst.get_device_type_id()
        if type_id in KNOWN_CALLBOXES:
            return CallboxType(type_id)
        else:
            raise ValueError(f"Unknown callbox type: {type_id}")


class _SCPIDevice(abstract_inst.SocketInstrument):
    """A generic SCPI callbox."""

    def get_device_type_id(self):
        """Queries the device instrument type string.

        Returns:
            device_type: the device type string.
        """
        self._send("*IDN?")
        resp = self._recv().split(",")
        if len(resp) < 2:
            raise RuntimeError(
                f"Unable to parse device type from SCPI response: {resp}"
            )

        return resp[1]

    def __enter__(self):
        self._connect_socket()
        return self

    def __exit__(self, *args):
        self._close_socket()
