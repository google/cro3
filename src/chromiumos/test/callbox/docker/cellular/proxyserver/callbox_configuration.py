# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Configuration managers for CrOS callboxes"""

from enum import Enum

from acts import logger
from acts.controllers import handover_simulator as hs
from acts.controllers.rohdeschwarz_lib import cmw500_cellular_simulator as cmw
from acts.controllers.rohdeschwarz_lib import cmx500_cellular_simulator as cmx
from acts.controllers.rohdeschwarz_lib.cmw500_handover_simulator import (
    Cmw500HandoverSimulator,
)
from cellular.callbox_utils.cmw500_iperf_measurement import (
    Cmw500IperfMeasurement,
)
from cellular.simulation_utils import CrOSLteSimulation


class CellularTechnology(Enum):
    """Supported cellular technologies."""

    LTE = "LTE"
    WCDMA = "WCDMA"
    NR5G_NSA = "NR5G_NSA"


# Maps CrOS CellularTechnology to ACTS handover CellularTechnologies
_HANDOVER_MAP = {
    CellularTechnology.LTE: hs.CellularTechnology.LTE,
    CellularTechnology.WCDMA: hs.CellularTechnology.WCDMA,
}


class CallboxConfiguration(object):
    """Base configuration for cellular callboxes."""

    def __init__(self):
        self.host = None
        self.port = None
        self.dut = None
        self.simulator = None
        self.simulation = None
        self.parameters = None
        self.iperf = None
        self.tx_measurement = None
        self.technology = None
        self.handover = None

    def lte_handover(self, band, channel, bw):
        """Performs a handover to LTE.

        Args:
            band: the band of the handover destination
            channel: the downlink channel of the handover destination
            bw: the downlink bandwidth of the handover destination
            source_technology: the source handover technology.
        """
        raise NotImplementedError()

    def wcdma_handover(self, band, channel):
        """Performs a handover to WCDMA.

        Args:
            band: the band of the handover destination
            channel: the downlink channel of the handover destination
            source_technology: the source handover technology.
        """
        raise NotImplementedError()

    def configure(self, parameters):
        """Configures the callbox with the provided parameters.

        Args:
            parameters: the callbox configuration dictionary.
        """
        raise NotImplementedError()

    def start(self):
        """Starts a simulation on the callbox."""
        self.simulation.start()

    def close(self):
        """Releases any resources held open by the controller."""
        self.simulator.destroy()

    def require_handover(self):
        """Verifies that handover simulations are available for the current callbox configuration.

        Raises:
            ValueError: If the feature is not supported for the current callbox configuration.
        """
        if self.handover is None:
            raise ValueError(
                f"Handovers are supported for RAT: {self.technology} in the current callbox configuration"
            )

    def require_simulation(self):
        """Verifies that CellularSimulator controls are available for the current callbox configuration.

        Raises:
            ValueError: If the feature is not supported for the current callbox configuration.
        """
        if self.simulation is None or self.simulator is None:
            raise ValueError(
                f"Action not supported for RAT: {self.technology} in the current callbox configuration"
            )

    def require_iperf(self):
        """Verifies that Iperf measurements are available for the current callbox configuration.

        Raises:
            ValueError: If the feature is not supported for the current callbox configuration.
        """
        if self.iperf is None:
            raise ValueError(
                f"Iperf not supported for RAT: {self.technology} in the current callbox configuration"
            )

    def require_tx_measurement(self):
        """Verifies that tx measurements are available for the current callbox configuration.

        Raises:
            ValueError: If the feature is not supported for the current callbox configuration.
        """
        if self.tx_measurement is None:
            raise ValueError(
                f"Tx measurement not supported for RAT: {self.technology} in the current callbox configuration"
            )


class CMW500Configuration(CallboxConfiguration):
    """Configuration for CMW500 callbox controller."""

    def __init__(self, dut, host, port, technology):
        """Initializes CMW500 controller configuration.

        Args:
            dut: a device handler implementing BaseCellularDut.
            host: the ip/host address of the callbox.
            port: the port number for the callbox controller commands.
            technology: the RAT technology.
        """
        super().__init__()

        self._lte_simulation = None
        self.dut = dut
        self.host = host
        self.port = port
        self.logger = logger.create_logger()
        self.technology = technology
        self.simulator = cmw.CMW500CellularSimulator(host, port)
        self.handover = Cmw500HandoverSimulator(self.simulator.cmw)
        self._set_technology(technology)

    def lte_handover(self, band, channel, bw):
        """Performs a handover to LTE.

        Args:
            band: the band of the handover destination
            channel: the downlink channel of the handover destination
            bw: the downlink bandwidth of the handover destination
            source_technology: the source handover technology.
        """
        if not self.technology in _HANDOVER_MAP:
            raise ValueError(
                f"Handover from {self.technology} is not supported in the current callbox configuration"
            )

        self.handover.lte_handover(
            band, channel, bw, _HANDOVER_MAP[self.technology]
        )
        self._set_technology(CellularTechnology.LTE)

    def wcdma_handover(self, band, channel):
        """Performs a handover to WCDMA.

        Args:
            band: the band of the handover destination
            channel: the downlink channel of the handover destination
            source_technology: the source handover technology.
        """
        if not self.technology in _HANDOVER_MAP:
            raise ValueError(
                f"Handover from {self.technology} is not supported in the current callbox configuration"
            )

        self.handover.wcdma_handover(
            band, channel, _HANDOVER_MAP[self.technology]
        )
        self._set_technology(CellularTechnology.WCDMA)

    def configure(self, parameters):
        """Configures the callbox with the provided parameters.

        Args:
            parameters: the callbox configuration dictionary.
        """
        self.simulation.stop()
        self.simulation.configure(parameters)
        self.simulator.wait_until_quiet()
        self.simulation.setup_simulator()

    def _set_technology(self, technology):
        """Switches the active simulation technology implementation."""
        if technology == CellularTechnology.LTE:
            self.iperf = Cmw500IperfMeasurement(self.simulator.cmw)
            self.tx_measurement = self.simulator.cmw.init_lte_measurement()

            # store lte_simulation since configuration is cleared when initializing
            if not self._lte_simulation:
                self._lte_simulation = CrOSLteSimulation.CrOSLteSimulation(
                    self.simulator,
                    self.logger,
                    self.dut,
                    {"attach_retries": 1, "attach_timeout": 120},
                    None,
                    power_mode=CrOSLteSimulation.PowerMode.RSRP,
                )
            self.simulation = self._lte_simulation
        elif technology == CellularTechnology.WCDMA:
            # no measurement/simulation available for WCDMA
            self.iperf = None
            self.tx_measurement = None
            self.simulation = None
        else:
            raise ValueError(f"Unsupported technology for CMW500: {technology}")

        self.technology = technology


class CMX500Configuration(CallboxConfiguration):
    """Configuration for CMX500 callboxes."""

    def __init__(self, dut, host, port, technology):
        """Initializes CMX500 controller configuration.

        Args:
            dut: a device handler implementing BaseCellularDut.
            host: the ip/host address of the callbox.
            port: the port number for the callbox controller commands.
            technology: the RAT technology.
        """
        super().__init__()

        self._lte_simulation = None
        self._nr5g_nsa_simulation = None
        self.dut = dut
        self.host = host
        self.port = port
        self.technology = technology
        self.logger = logger.create_logger()
        self.simulator = cmx.CMX500CellularSimulator(
            host, port, config_mode=None
        )

        self.handover = None
        self._set_technology(technology)

    def lte_handover(self, band, channel, bw):
        """Performs a handover to LTE.

        Args:
            band: the band of the handover destination
            channel: the downlink channel of the handover destination
            bw: the downlink bandwidth of the handover destination
            source_technology: the source handover technology.
        """
        # LTE handover not supported (yet) on CMX
        raise NotImplementedError()

    def wcdma_handover(self, band, channel):
        """Performs a handover to WCDMA.

        Args:
            band: the band of the handover destination
            channel: the downlink channel of the handover destination
            source_technology: the source handover technology.
        """
        # WCDMA handover not supported on CMX
        raise NotImplementedError()

    def configure(self, parameters):
        """Configures the callbox with the provided parameters.

        Args:
            parameters: the callbox configuration dictionary.
        """
        # no need to stop cmx before configuring like cmw, it's already
        # handled by cmx controller
        self.simulation.configure(parameters)
        self.simulator.wait_until_quiet()

    def start(self):
        """Starts a simulation on the callbox."""
        self.simulation.start()
        self.simulator.wait_until_quiet()

    def close(self):
        """Releases any resources held open by the controller."""
        self.simulator.destroy()

    def _set_technology(self, technology):
        """Switches the active simulation technology implementation."""
        self.iperf = None
        self.tx_measurement = None
        if technology == CellularTechnology.LTE:
            if not self._lte_simulation:
                self._lte_simulation = CrOSLteSimulation.CrOSLteSimulation(
                    self.simulator,
                    self.logger,
                    self.dut,
                    {"attach_retries": 1, "attach_timeout": 120},
                    None,
                    power_mode=CrOSLteSimulation.PowerMode.Total,
                )
            self.simulation = self._lte_simulation
        elif technology == CellularTechnology.NR5G_NSA:
            if not self._nr5g_nsa_simulation:
                self._nr5g_nsa_simulation = CrOSLteSimulation.CrOSLteSimulation(
                    self.simulator,
                    self.logger,
                    self.dut,
                    {"attach_retries": 1, "attach_timeout": 120},
                    None,
                    nr_mode="nr",
                    power_mode=CrOSLteSimulation.PowerMode.Total,
                )
            self.simulation = self._nr5g_nsa_simulation
        else:
            raise ValueError(f"Unsupported technology for CMW500: {technology}")

        self.technology = technology
