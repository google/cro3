# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Python module for Abstract Instrument Library."""

# pylint: disable=banned-string-format-function
# pylint: disable=C9010, W0612

import socket

from cellular import logger
import requests  # pylint: disable=E0401


class SocketInstrumentError(Exception):
    """Abstract Instrument Error Class, via Socket and SCPI."""

    def __init__(self, error, command=None):
        """Init method for Socket Instrument Error.

        Args:
            error: Exception error.
            command: Additional information on command,
                Type, Str.
        """
        super(SocketInstrumentError, self).__init__(error)
        self._error_code = error
        self._error_message = self._error_code
        if command is not None:
            self._error_message = "Command {} returned the error: {}.".format(
                repr(command), repr(self._error_message)
            )

    def __str__(self):
        return self._error_message


class SocketInstrument(object):
    """Abstract Instrument Class, via Socket and SCPI."""

    def __init__(self, ip_addr, ip_port):
        """Init method for Socket Instrument.

        Args:
            ip_addr: IP Address.
                Type, str.
            ip_port: TCPIP Port.
                Type, str.
        """
        self._socket_timeout = 120
        self._socket_buffer_size = 1024

        self._ip_addr = ip_addr
        self._ip_port = ip_port

        self._escseq = "\n"
        self._codefmt = "utf-8"

        self._logger = logger.create_tagged_trace_logger(
            "%s:%s" % (self._ip_addr, self._ip_port)
        )

        self._socket = None

    def _connect_socket(self):
        """Init and Connect to socket."""
        try:
            self._socket = socket.create_connection(
                (self._ip_addr, self._ip_port), timeout=self._socket_timeout
            )

            infmsg = "Opened Socket connection to {}:{} with handle {}.".format(
                repr(self._ip_addr), repr(self._ip_port), repr(self._socket)
            )
            self._logger.debug(infmsg)

        except socket.timeout:
            errmsg = "Socket timeout while connecting to instrument."
            self._logger.exception(errmsg)
            raise SocketInstrumentError(errmsg)

        except socket.error:
            errmsg = "Socket error while connecting to instrument."
            self._logger.exception(errmsg)
            raise SocketInstrumentError(errmsg)

    def _send(self, cmd):
        """Send command via Socket.

        Args:
            cmd: Command to send,
                Type, Str.
        """
        if not self._socket:
            self._logger.warning("Socket instrument is not connected")
            self._connect_socket()

        cmd_es = cmd + self._escseq

        try:
            self._socket.sendall(cmd_es.encode(self._codefmt))
            self._logger.debug(
                "Sent %r to %r:%r.", cmd, self._ip_addr, self._ip_port
            )

        except socket.timeout:
            errmsg = (
                "Socket timeout while sending command {} " "to instrument."
            ).format(repr(cmd))
            self._logger.exception(errmsg)
            raise SocketInstrumentError(errmsg)

        except socket.error:
            errmsg = (
                "Socket error while sending command {} " "to instrument."
            ).format(repr(cmd))
            self._logger.exception(errmsg)
            raise SocketInstrumentError(errmsg)

        except Exception as err:
            errmsg = (
                "Error {} while sending command {} " "to instrument."
            ).format(repr(cmd), repr(err))
            self._logger.exception(errmsg)
            raise

    def _recv(self):
        """Receive response via Socket.

        Returns:
            resp: Response from Instrument via Socket,
                Type, Str.
        """
        if not self._socket:
            self._logger.warning("Socket instrument is not connected")
            self._connect_socket()

        resp = ""

        try:
            while True:
                resp_tmp = self._socket.recv(self._socket_buffer_size)
                resp_tmp = resp_tmp.decode(self._codefmt)
                resp += resp_tmp
                if len(resp_tmp) < self._socket_buffer_size:
                    break

        except socket.timeout:
            errmsg = "Socket timeout while receiving response from instrument."
            self._logger.exception(errmsg)
            raise SocketInstrumentError(errmsg)

        except socket.error:
            errmsg = "Socket error while receiving response from instrument."
            self._logger.exception(errmsg)
            raise SocketInstrumentError(errmsg)

        except Exception as err:
            errmsg = (
                "Error {} while receiving response " "from instrument"
            ).format(repr(err))
            self._logger.exception(errmsg)
            raise

        resp = resp.rstrip(self._escseq)

        self._logger.debug(
            "Received %r from %r:%r.", resp, self._ip_addr, self._ip_port
        )

        return resp

    def _close_socket(self):
        """Close Socket Instrument."""
        if not self._socket:
            return

        try:
            self._socket.shutdown(socket.SHUT_RDWR)
            self._socket.close()
            self._socket = None
            self._logger.debug(
                "Closed Socket Instrument %r:%r.", self._ip_addr, self._ip_port
            )

        except Exception as err:
            errmsg = "Error {} while closing instrument.".format(repr(err))
            self._logger.exception(errmsg)
            raise

    def _query(self, cmd):
        """query instrument via Socket.

        Args:
            cmd: Command to send,
                Type, Str.

        Returns:
            resp: Response from Instrument via Socket,
                Type, Str.
        """
        self._send(cmd + ";*OPC?")
        resp = self._recv()
        return resp


class RequestInstrument(object):
    """Abstract Instrument Class, via Request."""

    def __init__(self, ip_addr):
        """Init method for request instrument.

        Args:
            ip_addr: IP Address.
                Type, Str.
        """
        self._request_timeout = 120
        self._request_protocol = "http"
        self._ip_addr = ip_addr
        self._escseq = "\r\n"

        self._logger = logger.create_tagged_trace_logger(self._ip_addr)

    def _query(self, cmd):
        """query instrument via request.

        Args:
            cmd: Command to send,
                Type, Str.

        Returns:
            resp: Response from Instrument via request,
                Type, Str.
        """
        request_cmd = "{}://{}/{}".format(
            self._request_protocol, self._ip_addr, cmd
        )
        resp_raw = requests.get(request_cmd, timeout=self._request_timeout)

        resp = resp_raw.text
        for char_del in self._escseq:
            resp = resp.replace(char_del, "")

        self._logger.debug(
            "Sent %r to %r, and get %r.", cmd, self._ip_addr, resp
        )

        return resp
