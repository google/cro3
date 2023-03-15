# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides ChromeOS-specific LTE simulation implementations."""

from enum import Enum

from acts.controllers.cellular_lib.BaseCellConfig import BaseCellConfig
from acts.controllers.cellular_lib.LteSimulation import LteSimulation


class PowerMode(Enum):
    """The power mode used on the callbox."""

    Total = "Total"
    RSRP = "RSRP"


class CrOSLteSimulation(LteSimulation):
    """ChromeOS-specific LTE simulation."""

    # RSRP signal levels thresholds taken from cellular_capability_3gpp.cc
    DOWNLINK_SIGNAL_LEVEL_DICTIONARY = {
        "excellent": -88,
        "high": -98,
        "medium": -108,
        "weak": -118,
        "disconnected": -170,
    }

    def __init__(
        self,
        simulator,
        log,
        dut,
        test_config,
        calibration_table,
        nr_mode=None,
        power_mode=PowerMode.Total,
    ):
        """Initializes the simulator for a single-carrier LTE simulation.

        Args:
            simulator: a cellular simulator controller
            log: a logger handle
            dut: a device handler implementing BaseCellularDut
            test_config: test configuration obtained from the config file
            calibration_table: a dictionary containing path losses for
                different bands.
            nr_mode: a string defining the simulation nr mode to use.
            power_mode: a PowerMode describing the expected output power
                specification mode to use on the callbox.
        """
        super().__init__(
            simulator, log, dut, test_config, calibration_table, nr_mode
        )

        self._power_mode = power_mode

    def attach(self):
        """Attach the phone to the basestation.

        ACTS sets separate Tx/Rx values when attaching to ensure a good
        connection when attaching to attach to.

        CrOSLteSimulation overrides this to:
            1. set different Rx power values from those in ACTS since CrOS won't
                attach if the power level is too high.
            2. set the final Tx power before attaching since large swings in tx
                power can cause the callbox connection to be unstable.
        """
        # temporarily set tx power on primary carrier
        attach_power = max(self.DOWNLINK_SIGNAL_LEVEL_DICTIONARY.values())
        self.set_downlink_rx_power(attach_power)

        # set rx power to final value.
        self.set_uplink_tx_power(self.sim_ul_power)
        self.simulator.wait_until_attached(timeout=self.attach_timeout)
        return True

    def start(self):
        """Start the simulation by attaching the phone and setting the required DL and UL power.

        CrOSLteSimulation overrides this to set different values from those in ACTS
        """
        if not self.attach():
            raise RuntimeError("Could not attach to base station.")

        self.simulator.wait_until_communication_state()

        for bts_idx in range(self.num_carriers):
            new_config = BaseCellConfig(self.log)
            new_config.output_power = self.calibrated_downlink_rx_power(
                self.cell_configs[bts_idx], self.sim_dl_power
            )
            self.simulator.configure_bts(new_config)
            self.cell_configs[bts_idx].incorporate(new_config)

        if self.num_carriers > 1:
            self.simulator.lte_attach_secondary_carriers(self.freq_bands)

    def get_uplink_tx_power(self):
        """Returns the uplink tx power level

        Returns:
            calibrated tx power in dBm
        """
        return self.cell_configs[0].input_power

    def get_downlink_rx_power(self):
        """Returns the downlink tx power level

        Returns:
            calibrated rx power in dBm
        """
        return self.cell_configs[0].output_power

    def calibrated_downlink_rx_power(self, bts_config, rsrp):
        """Calibrates the downlink power to account for pathloss."""
        # if output power should be total cell power then convert RSRP to total.
        if self._power_mode == PowerMode.Total:
            rsrp = self.rsrp_to_signal_power(rsrp, bts_config)

        # don't calibrate here, calibration is handled by the remote host
        return rsrp

    def calibrated_uplink_tx_power(self, bts_config, signal_level):
        """Calibrates the uplink power to account for pathloss."""
        # don't calibrate here, calibration is handled by the remote host
        return signal_level

    def get_uplink_power_from_parameters(self, parameters):
        """Reads uplink power from a list of parameters."""
        if BaseCellConfig.PARAM_UL_PW in parameters:
            value = parameters[BaseCellConfig.PARAM_UL_PW]
            if value in self.UPLINK_SIGNAL_LEVEL_DICTIONARY:
                return self.UPLINK_SIGNAL_LEVEL_DICTIONARY[value]
            else:
                if isinstance(value[0], str) and value[0] == "n":
                    # Treat the 'n' character as a negative sign
                    return -float(value[1:])
                else:
                    return float(value)

        return max(self.UPLINK_SIGNAL_LEVEL_DICTIONARY.values())

    def get_downlink_power_from_parameters(self, parameters):
        """Reads downlink power from a list of parameters."""
        if BaseCellConfig.PARAM_DL_PW in parameters:
            value = parameters[BaseCellConfig.PARAM_DL_PW]
            if value in self.DOWNLINK_SIGNAL_LEVEL_DICTIONARY:
                return self.DOWNLINK_SIGNAL_LEVEL_DICTIONARY[value]
            else:
                if isinstance(value[0], str) and value[0] == "n":
                    # Treat the 'n' character as a negative sign
                    return -float(value[1:])
                else:
                    return float(value)

        return max(self.DOWNLINK_SIGNAL_LEVEL_DICTIONARY.values())
