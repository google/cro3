# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides ChromeOS-specific LTE simulation implementations."""

from cellular.simulation_utils.BaseCellConfig import BaseCellConfig
from cellular.simulation_utils.LteSimulation import LteSimulation


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
