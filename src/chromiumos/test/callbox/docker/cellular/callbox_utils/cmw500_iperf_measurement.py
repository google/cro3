# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides classes for managing Iperf sessions on cmw500 callboxes."""

# disable some lints to stay consistent with ACTS formatting
# pylint: disable=banned-string-format-function

from enum import Enum
import time


class IperfType(Enum):
    """Supported performance measurement types"""
    IPERF = 'IPER'
    IPERF3 = 'IP3'
    # NAT = 'NAT' # unsupported


class IperfProtocolType(Enum):
    """Supported protocol types"""
    TCP = 'TCP'
    UDP = 'UDP'


class IperfMeasurementState(Enum):
    """Possible measurement states"""
    OFF = 'OFF'
    READY = 'RDY'
    RUN = 'RUN'


class Cmw500IperfMeasurement(object):
    """Class for measuring cellular performance via Iperf."""

    DEFAULT_TEST_TYPE = IperfType.IPERF
    DEFAULT_TIME = 30
    DEFAULT_PACKET_SIZE = 1470
    DEFAULT_PORT = 5001
    DEFAULT_WINDOW_SIZE = 10240
    DEFAULT_MAX_BITRATE = 0
    DEFAULT_PARALLEL_CONNECTIONS = 4

    PARAM_TEST_TYPE = 'type'
    PARAM_TIME = 'time'
    PARAM_PACKET_SIZE = 'psize'
    PARAM_SERVERS = 'servers'
    PARAM_CLIENTS = 'clients'

    PARAM_IP_ADDRESS = 'ip'
    PARAM_PROTOCOL = 'proto'
    PARAM_PORT = 'port'
    PARAM_WINDOW_SIZE = 'wsize'
    PARAM_MAX_BITRATE = 'mbitrate'
    PARAM_PARALLEL_CONNECTIONS = 'pconnections'

    def __init__(self, cmw, idx=1):
        self._cmw = cmw
        self._idx = idx
        self.clients = [CMW500IperfClient(cmw, idx, i + 1) for i in range(8)]
        self.servers = [CMW500IperfServer(cmw, idx, i + 1) for i in range(8)]

    def configure(self, parameters):
        """Configures measurement using a dictionary of parameters.

        Args:
            parameters: a configuration dictionary
        """
        self.test_type = self._get_parameter(self.PARAM_TEST_TYPE,
                                             parameters,
                                             default=self.DEFAULT_TEST_TYPE,
                                             fun=IperfType)
        self.test_time = self._get_parameter(self.PARAM_TIME,
                                             parameters,
                                             default=self.DEFAULT_TIME,
                                             fun=int)
        self.packet_size = self._get_parameter(
            self.PARAM_PACKET_SIZE,
            parameters,
            default=self.DEFAULT_PACKET_SIZE,
            fun=int)

        if self.PARAM_CLIENTS in parameters:
            client_configs = parameters[self.PARAM_CLIENTS]
            for i, client_config in enumerate(client_configs):
                client = self.clients[i]
                client.enabled = True

                client.ip_address = self._get_parameter(self.PARAM_IP_ADDRESS,
                                                        client_config,
                                                        required=True)
                client.protocol = self._get_parameter(self.PARAM_PROTOCOL,
                                                      client_config,
                                                      required=True,
                                                      fun=IperfProtocolType)
                client.port = self._get_parameter(self.PARAM_PORT,
                                                  client_config,
                                                  default=self.DEFAULT_PORT,
                                                  fun=int)
                client.window_size = self._get_parameter(
                    self.PARAM_WINDOW_SIZE,
                    client_config,
                    default=self.DEFAULT_WINDOW_SIZE,
                    fun=int)

                if client.protocol == IperfProtocolType.UDP:
                    client.max_bitrate = self._get_parameter(
                        self.PARAM_MAX_BITRATE,
                        client_config,
                        default=self.DEFAULT_MAX_BITRATE,
                        fun=float)
                if client.protocol == IperfProtocolType.TCP:
                    client.parallel_connections = self._get_parameter(
                        self.PARAM_PARALLEL_CONNECTIONS,
                        client_config,
                        default=self.DEFAULT_PARALLEL_CONNECTIONS,
                        fun=int)

        if self.PARAM_SERVERS in parameters:
            server_configs = parameters[self.PARAM_SERVERS]
            for i, server_config in enumerate(server_configs):
                server = self.servers[i]
                server.enabled = True

                server.protocol = self._get_parameter(self.PARAM_PROTOCOL,
                                                      server_config,
                                                      required=True,
                                                      fun=IperfProtocolType)
                server.port = self._get_parameter(self.PARAM_PORT,
                                                  server_config,
                                                  default=self.DEFAULT_PORT,
                                                  fun=int)
                server.window_size = self._get_parameter(
                    self.PARAM_WINDOW_SIZE,
                    server_config,
                    default=self.DEFAULT_WINDOW_SIZE,
                    fun=int)

        # disable all other clients and servers not specified
        client_count = len(parameters[
            self.PARAM_CLIENTS]) if self.PARAM_CLIENTS in parameters else 0
        for i in range(client_count, len(self.clients)):
            self.clients[i].enabled = False
        server_count = len(parameters[
            self.PARAM_SERVERS]) if self.PARAM_SERVERS in parameters else 0
        for i in range(server_count, len(self.clients)):
            self.servers[i].enabled = False

    @property
    def ip_address(self):
        """Gets the current DAU IP address."""
        cmd = 'SENSe:DATA:CONTrol:IPVFour:CURRent:IPADdress?'
        return self._cmw.send_and_recv(cmd).strip('"\'')

    @property
    def test_time(self):
        """Gets the performance test duration."""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:TDURation?'.format(self._idx)
        return int(self._cmw.send_and_recv(cmd))

    @test_time.setter
    def test_time(self, duration):
        """Sets the performance test duration.

        Args:
            duration: length of the performance test.
        """
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:TDURation {}'.format(
            self._idx, duration)
        self._cmw.send_and_recv(cmd)

    @property
    def test_type(self):
        """Gets the type of performance test to be run."""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:TYPE?'.format(self._idx)
        return IperfType(self._cmw.send_and_recv(cmd))

    @test_type.setter
    def test_type(self, mode):
        """Sets the type of performance test to run.

        Args:
            mode: IPER/IP3
        """
        if not isinstance(mode, IperfType):
            raise ValueError('mode should be the instance of IperfType')

        cmd = 'CONFigure:DATA:MEAS{}:IPERf:TYPE {}'.format(
            self._idx, mode.value)
        self._cmw.send_and_recv(cmd)

    @property
    def packet_size(self):
        """Gets the performance test packet size."""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:PSIZe?'.format(self._idx)
        return int(self._cmw.send_and_recv(cmd))

    @packet_size.setter
    def packet_size(self, size):
        """Sets the performance test packet size

        Args:
            size: the packet size
        """
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:PSIZe {}'.format(self._idx, size)
        self._cmw.send_and_recv(cmd)

    @property
    def state(self):
        """Gets the current state of the measurement"""
        cmd = 'FETCh:DATA:MEAS{}:IPERf:STATe?'.format(self._idx)
        return IperfMeasurementState(self._cmw.send_and_recv(cmd))

    def start(self):
        """Starts the performance measurement on the callbox"""
        if self.test_type != IperfType.IPERF:
            raise CmwIperfError(
                'Unable to run performance test, test type {} not supported'.
                format(self.test_type))

        cmd = 'INITiate:DATA:MEAS{}:IPERf'.format(self._idx)
        self._cmw.send_and_recv(cmd)
        self._wait_for_state(
            {IperfMeasurementState.RUN, IperfMeasurementState.READY})

    def stop(self):
        """Halts the measurement immediately and puts it the RDY state."""
        cmd = 'STOP:DATA:MEAS{}:IPERf'.format(self._idx)
        self._cmw.send_and_recv(cmd)
        self._wait_for_state(
            {IperfMeasurementState.OFF, IperfMeasurementState.READY})

    def close(self):
        """Halts the measurement immediately and puts it the OFF state."""
        cmd = 'ABORt:DATA:MEAS{}:IPERf'.format(self._idx)
        self._cmw.send_and_recv(cmd)
        self._wait_for_state({IperfMeasurementState.OFF})

    def query_results(self):
        """Queries the current measurement results

        Results are updated in 1 second intervals. A result's
        "counter" can be used to differentiate between individual results.

        Returns:
            A dictionary containing the results for all servers and clients.
            Invalid results are set to None.
        """
        results = self._cmw.send_and_recv(
            'FETCh:DATA:MEAS{}:IPERf:ALL?'.format(self._idx))
        results = results.split(',')
        reliability = self._try_parse(results[0], float)

        output = {'reliability': reliability, 'servers': [], 'clients': []}
        for i in range(1, len(results), 5):
            server_counter = self._try_parse(results[i], int)
            client_counter = self._try_parse(results[i + 1], int)
            uplink_throughput = self._try_parse(results[i + 2], float)
            loss_rate = self._try_parse(results[i + 3], float)
            downlink_throughput = self._try_parse(results[i + 4], float)

            if (server_counter is None or uplink_throughput is None
                    or loss_rate is None):
                server = None
            else:
                server = {
                    'counter': server_counter,
                    'throughput': uplink_throughput,
                    'loss': loss_rate,
                }

            if client_counter is None or downlink_throughput is None:
                client = None
            else:
                client = {
                    'counter': client_counter,
                    'throughput': downlink_throughput,
                }

            output['servers'].append(server)
            output['clients'].append(client)

        return output

    def _wait_for_state(self, states, timeout=10):
        """Polls the measurement state until it reaches an allowable state

        Args:
            states: the allowed states
            timeout: the maximum amount time to wait
        """
        while timeout > 0:
            if self.state in states:
                return

            time.sleep(1)
            timeout -= 1

        raise CmwIperfError('Failed enter Iperf state: {}.'.format(states))

    @staticmethod
    def _try_parse(s, fun):
        try:
            return fun(s)
        except ValueError:
            return None

    @staticmethod
    def _get_parameter(name,
                       parameters,
                       default=None,
                       fun=None,
                       required=False):
        if name in parameters:
            return parameters[name] if fun is None else fun(parameters[name])
        elif required:
            raise ValueError(
                "The configuration dictionary must include a key '{}'".format(
                    name))
        elif default is not None:
            return default


class CMW500IperfClient(object):
    """Class for controlling a single client Iperf instance."""

    def __init__(self, cmw, measIdx, idx):
        self._cmw = cmw
        self._measIdx = measIdx
        self._idx = idx

    @property
    def enabled(self):
        """Gets if the client is enabled."""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:ENABle?'.format(
            self._measIdx, self._idx)
        return self._cmw.send_and_recv(cmd) == 'ON'

    @enabled.setter
    def enabled(self, enabled):
        """Sets if the client is enabled.

        Args:
            enabled: True/False
        """
        on = 'ON' if enabled else 'OFF'
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:ENABle {}'.format(
            self._measIdx, self._idx, on)
        self._cmw.send_and_recv(cmd)

    @property
    def protocol(self):
        """Gets the protocol that the client uses."""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:PROTocol?'.format(
            self._measIdx, self._idx)
        return IperfProtocolType(self._cmw.send_and_recv(cmd))

    @protocol.setter
    def protocol(self, protocol):
        """Sets the protocol that the client uses.

        Args:
            protocol: TCP/UDP
        """
        if not isinstance(protocol, IperfProtocolType):
            raise ValueError(
                'protocol should be the instance of IperfProtocolType')

        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:PROTocol {}'.format(
            self._measIdx, self._idx, protocol.value)
        self._cmw.send_and_recv(cmd)

    @property
    def port(self):
        """Gets the port that that the client uses."""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:PORT?'.format(
            self._measIdx, self._idx)
        return int(self._cmw.send_and_recv(cmd))

    @port.setter
    def port(self, port):
        """Gets the protocol that the client uses.

        Args:
            port: the port number to use
        """
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:PORT {}'.format(
            self._measIdx, self._idx, port)
        self._cmw.send_and_recv(cmd)

    @property
    def window_size(self):
        """Gets the window size that the client uses."""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:SBSize?'.format(
            self._measIdx, self._idx)
        return int(self._cmw.send_and_recv(cmd))

    @window_size.setter
    def window_size(self, size):
        """Sets the window size that the client uses.

        Args:
            size: int
        """
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:SBSize {}'.format(
            self._measIdx, self._idx, size)
        self._cmw.send_and_recv(cmd)

    @property
    def ip_address(self):
        """Returns the IP address that the client uses."""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:IPADdress?'.format(
            self._measIdx, self._idx)
        return self._cmw.send_and_recv(cmd).strip('"\'')

    @ip_address.setter
    def ip_address(self, address):
        """Sets the IP address that the client uses.

        Args:
            address: ip address of the Iperf server
        """
        cmd = "CONFigure:DATA:MEAS{}:IPERf:CLIent{}:IPADdress '{}'".format(
            self._measIdx, self._idx, address)
        self._cmw.send_and_recv(cmd)

    @property
    def parallel_connections(self):
        """Gets the number of parallel connections the client uses (TCP only)"""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:PCONnection?'.format(
            self._measIdx, self._idx)
        return int(self._cmw.send_and_recv(cmd))

    @parallel_connections.setter
    def parallel_connections(self, parallel_count):
        """Sets the number of parallel connections the client uses (TCP only)

        Args:
            parallel_count: number of parallel connections to use
        """
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:PCONnection {}'.format(
            self._measIdx, self._idx, parallel_count)
        self._cmw.send_and_recv(cmd)

    @property
    def max_bitrate(self):
        """Gets the client's maximum bitrate (only applies when in UDP)"""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:BITRate?'.format(
            self._measIdx, self._idx)
        return float(self._cmw.send_and_recv(cmd))

    @max_bitrate.setter
    def max_bitrate(self, bitrate):
        """Sets the client's maximum bitrate (only applies when in UDP)

        Args:
            bitrate: the maximum bitrate for the client to use
        """
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:CLIent{}:BITRate {}'.format(
            self._measIdx, self._idx, bitrate)
        self._cmw.send_and_recv(cmd)


class CMW500IperfServer(object):
    """Class for controlling a single callbox Iperf server instance."""

    def __init__(self, cmw, measIdx, idx):
        self._cmw = cmw
        self._measIdx = measIdx
        self._idx = idx

    @property
    def enabled(self):
        """Gets if the server is enabled."""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:SERVer{}:ENABle?'.format(
            self._measIdx, self._idx)
        return self._cmw.send_and_recv(cmd) == 'ON'

    @enabled.setter
    def enabled(self, enabled):
        """Sets if the server is enabled.

        Args:
            enabled: True/False
        """
        on = 'ON' if enabled else 'OFF'
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:SERVer{}:ENABle {}'.format(
            self._measIdx, self._idx, on)
        self._cmw.send_and_recv(cmd)

    @property
    def protocol(self):
        """Gets the protocol that the server uses."""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:SERVer{}:PROTocol?'.format(
            self._measIdx, self._idx)
        return IperfProtocolType(self._cmw.send_and_recv(cmd))

    @protocol.setter
    def protocol(self, protocol):
        """Sets the protocol that the server uses.

        Args:
            protocol: TCP/UDP
        """
        if not isinstance(protocol, IperfProtocolType):
            raise ValueError(
                'protocol should be the instance of IperfProtocolType')

        cmd = 'CONFigure:DATA:MEAS{}:IPERf:SERVer{}:PROTocol {}'.format(
            self._measIdx, self._idx, protocol.value)
        self._cmw.send_and_recv(cmd)

    @property
    def port(self):
        """Gets the port that that the server uses."""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:SERVer{}:PORT?'.format(
            self._measIdx, self._idx)
        return int(self._cmw.send_and_recv(cmd))

    @port.setter
    def port(self, port):
        """Gets the protocol that the server uses.

        Args:
            port: the port number to use
        """
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:SERVer{}:PORT {}'.format(
            self._measIdx, self._idx, port)
        self._cmw.send_and_recv(cmd)

    @property
    def window_size(self):
        """Gets the window size that the server uses."""
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:SERVer{}:SBSize?'.format(
            self._measIdx, self._idx)
        return int(self._cmw.send_and_recv(cmd))

    @window_size.setter
    def window_size(self, size):
        """Sets the window size that the server uses.

        Args:
            size: the window size to use
        """
        cmd = 'CONFigure:DATA:MEAS{}:IPERf:SERVer{}:SBSize {}'.format(
            self._measIdx, self._idx, size)
        self._cmw.send_and_recv(cmd)


class CmwIperfError(Exception):
    """Class to raise exceptions related to cmw Iperf."""
