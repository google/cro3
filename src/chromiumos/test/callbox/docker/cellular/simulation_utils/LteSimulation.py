# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(b/254347891): unify formatting and ignore specific lints in callbox libraries
# pylint: skip-file

from enum import Enum
import math
import time

from cellular.simulation_utils import BaseCellularDut
from cellular.simulation_utils.BaseSimulation import BaseSimulation
from cellular.simulation_utils.LteCellConfig import LteCellConfig
from cellular.simulation_utils.NrCellConfig import NrCellConfig


class TransmissionMode(Enum):
    """Transmission modes for LTE (e.g., TM1, TM4, ...)"""

    TM1 = "TM1"
    TM2 = "TM2"
    TM3 = "TM3"
    TM4 = "TM4"
    TM7 = "TM7"
    TM8 = "TM8"
    TM9 = "TM9"


class MimoMode(Enum):
    """Mimo modes"""

    MIMO_1x1 = "1x1"
    MIMO_2x2 = "2x2"
    MIMO_4x4 = "4x4"


class SchedulingMode(Enum):
    """Traffic scheduling modes (e.g., STATIC, DYNAMIC)"""

    DYNAMIC = "DYNAMIC"
    STATIC = "STATIC"


class DuplexMode(Enum):
    """DL/UL Duplex mode"""

    FDD = "FDD"
    TDD = "TDD"


class ModulationType(Enum):
    """DL/UL Modulation order."""

    QPSK = "QPSK"
    Q16 = "16QAM"
    Q64 = "64QAM"
    Q256 = "256QAM"


# Bandwidth [MHz] to RB group size
RBG_DICTIONARY = {20: 4, 15: 4, 10: 3, 5: 2, 3: 2, 1.4: 1}

# Bandwidth [MHz] to total RBs mapping
TOTAL_RBS_DICTIONARY = {20: 100, 15: 75, 10: 50, 5: 25, 3: 15, 1.4: 6}

# Bandwidth [MHz] to minimum number of DL RBs that can be assigned to a UE
MIN_DL_RBS_DICTIONARY = {20: 16, 15: 12, 10: 9, 5: 4, 3: 4, 1.4: 2}

# Bandwidth [MHz] to minimum number of UL RBs that can be assigned to a UE
MIN_UL_RBS_DICTIONARY = {20: 8, 15: 6, 10: 4, 5: 2, 3: 2, 1.4: 1}


class LteSimulation(BaseSimulation):
    """Single-carrier LTE simulation."""

    # Test config keywords
    KEY_FREQ_BANDS = "freq_bands"

    # Cell param keywords
    PARAM_RRC_STATUS_CHANGE_TIMER = "rrcstatuschangetimer"

    # Units in which signal level is defined in DOWNLINK_SIGNAL_LEVEL_DICTIONARY
    DOWNLINK_SIGNAL_LEVEL_UNITS = "RSRP"

    # RSRP signal levels thresholds (as reported by Android) in dBm/15KHz.
    # Excellent is set to -75 since callbox B Tx power is limited to -30 dBm
    DOWNLINK_SIGNAL_LEVEL_DICTIONARY = {
        "excellent": -75,
        "high": -110,
        "medium": -115,
        "weak": -120,
        "disconnected": -170,
    }

    # Transmitted output power for the phone (dBm)
    UPLINK_SIGNAL_LEVEL_DICTIONARY = {
        "max": 27,
        "high": 13,
        "medium": 3,
        "low": -20,
    }

    # Allowed bandwidth for each band.
    allowed_bandwidth_dictionary = {
        1: [5, 10, 15, 20],
        2: [1.4, 3, 5, 10, 15, 20],
        3: [1.4, 3, 5, 10, 15, 20],
        4: [1.4, 3, 5, 10, 15, 20],
        5: [1.4, 3, 5, 10],
        7: [5, 10, 15, 20],
        8: [1.4, 3, 5, 10],
        10: [5, 10, 15, 20],
        11: [5, 10],
        12: [1.4, 3, 5, 10],
        13: [5, 10],
        14: [5, 10],
        17: [5, 10],
        18: [5, 10, 15],
        19: [5, 10, 15],
        20: [5, 10, 15, 20],
        21: [5, 10, 15],
        22: [5, 10, 15, 20],
        24: [5, 10],
        25: [1.4, 3, 5, 10, 15, 20],
        26: [1.4, 3, 5, 10, 15],
        27: [1.4, 3, 5, 10],
        28: [3, 5, 10, 15, 20],
        29: [3, 5, 10],
        30: [5, 10],
        31: [1.4, 3, 5],
        32: [5, 10, 15, 20],
        33: [5, 10, 15, 20],
        34: [5, 10, 15],
        35: [1.4, 3, 5, 10, 15, 20],
        36: [1.4, 3, 5, 10, 15, 20],
        37: [5, 10, 15, 20],
        38: [20],
        39: [5, 10, 15, 20],
        40: [5, 10, 15, 20],
        41: [5, 10, 15, 20],
        42: [5, 10, 15, 20],
        43: [5, 10, 15, 20],
        44: [3, 5, 10, 15, 20],
        45: [5, 10, 15, 20],
        46: [10, 20],
        47: [10, 20],
        48: [5, 10, 15, 20],
        49: [10, 20],
        50: [3, 5, 10, 15, 20],
        51: [3, 5],
        52: [5, 10, 15, 20],
        65: [5, 10, 15, 20],
        66: [1.4, 3, 5, 10, 15, 20],
        67: [5, 10, 15, 20],
        68: [5, 10, 15],
        69: [5],
        70: [5, 10, 15],
        71: [5, 10, 15, 20],
        72: [1.4, 3, 5],
        73: [1.4, 3, 5],
        74: [1.4, 3, 5, 10, 15, 20],
        75: [5, 10, 15, 20],
        76: [5],
        85: [5, 10],
        252: [20],
        255: [20],
    }

    # Dictionary of lower DL channel number bound for each band.
    LOWEST_DL_CN_DICTIONARY = {
        1: 0,
        2: 600,
        3: 1200,
        4: 1950,
        5: 2400,
        6: 2650,
        7: 2750,
        8: 3450,
        9: 3800,
        10: 4150,
        11: 4750,
        12: 5010,
        13: 5180,
        14: 5280,
        17: 5730,
        18: 5850,
        19: 6000,
        20: 6150,
        21: 6450,
        22: 6600,
        23: 7500,
        24: 7700,
        25: 8040,
        26: 8690,
        27: 9040,
        28: 9210,
        29: 9660,
        30: 9770,
        31: 9870,
        32: 9920,
        33: 36000,
        34: 36200,
        35: 36350,
        36: 36950,
        37: 37550,
        38: 37750,
        39: 38250,
        40: 38650,
        41: 39650,
        42: 41590,
        43: 45590,
        66: 66436,
        67: 67336,
    }

    # Peak throughput lookup tables for each TDD subframe
    # configuration and bandwidth
    # yapf: disable
    tdd_config4_tput_lut = {
        0: {
            5: {'DL': 3.82, 'UL': 2.63},
            10: {'DL': 11.31,'UL': 9.03},
            15: {'DL': 16.9, 'UL': 20.62},
            20: {'DL': 22.88, 'UL': 28.43}
        },
        1: {
            5: {'DL': 6.13, 'UL': 4.08},
            10: {'DL': 18.36, 'UL': 9.69},
            15: {'DL': 28.62, 'UL': 14.21},
            20: {'DL': 39.04, 'UL': 19.23}
        },
        2: {
            5: {'DL': 5.68, 'UL': 2.30},
            10: {'DL': 25.51, 'UL': 4.68},
            15: {'DL': 39.3, 'UL': 7.13},
            20: {'DL': 53.64, 'UL': 9.72}
        },
        3: {
            5: {'DL': 8.26, 'UL': 3.45},
            10: {'DL': 23.20, 'UL': 6.99},
            15: {'DL': 35.35, 'UL': 10.75},
            20: {'DL': 48.3, 'UL': 14.6}
        },
        4: {
            5: {'DL': 6.16, 'UL': 2.30},
            10: {'DL': 26.77, 'UL': 4.68},
            15: {'DL': 40.7, 'UL': 7.18},
            20: {'DL': 55.6, 'UL': 9.73}
        },
        5: {
            5: {'DL': 6.91, 'UL': 1.12},
            10: {'DL': 30.33, 'UL': 2.33},
            15: {'DL': 46.04, 'UL': 3.54},
            20: {'DL': 62.9, 'UL': 4.83}
        },
        6: {
            5: {'DL': 6.13, 'UL': 4.13},
            10: {'DL': 14.79, 'UL': 11.98},
            15: {'DL': 23.28, 'UL': 17.46},
            20: {'DL': 31.75, 'UL': 23.95}
        }
    }

    tdd_config3_tput_lut = {
        0: {
            5: {'DL': 5.04, 'UL': 3.7},
            10: {'DL': 15.11, 'UL': 17.56},
            15: {'DL': 22.59, 'UL': 30.31},
            20: {'DL': 30.41, 'UL': 41.61}
        },
        1: {
            5: {'DL': 8.07, 'UL': 5.66},
            10: {'DL': 24.58, 'UL': 13.66},
            15: {'DL': 39.05, 'UL': 20.68},
            20: {'DL': 51.59, 'UL': 28.76}
        },
        2: {
            5: {'DL': 7.59, 'UL': 3.31},
            10: {'DL': 34.08, 'UL': 6.93},
            15: {'DL': 53.64, 'UL': 10.51},
            20: {'DL': 70.55, 'UL': 14.41}
        },
        3: {
            5: {'DL': 10.9, 'UL': 5.0},
            10: {'DL': 30.99, 'UL': 10.25},
            15: {'DL': 48.3, 'UL': 15.81},
            20: {'DL': 63.24, 'UL': 21.65}
        },
        4: {
            5: {'DL': 8.11, 'UL': 3.32},
            10: {'DL': 35.74, 'UL': 6.95},
            15: {'DL': 55.6, 'UL': 10.51},
            20: {'DL': 72.72, 'UL': 14.41}
        },
        5: {
            5: {'DL': 9.28, 'UL': 1.57},
            10: {'DL': 40.49, 'UL': 3.44},
            15: {'DL': 62.9, 'UL': 5.23},
            20: {'DL': 82.21, 'UL': 7.15}
        },
        6: {
            5: {'DL': 8.06, 'UL': 5.74},
            10: {'DL': 19.82, 'UL': 17.51},
            15: {'DL': 31.75, 'UL': 25.77},
            20: {'DL': 42.12, 'UL': 34.91}
        }
    }

    tdd_config2_tput_lut = {
        0: {
            5: {'DL': 3.11, 'UL': 2.55},
            10: {'DL': 9.93, 'UL': 11.1},
            15: {'DL': 13.9, 'UL': 21.51},
            20: {'DL': 20.02, 'UL': 41.66}
        },
        1: {
            5: {'DL': 5.33, 'UL': 4.27},
            10: {'DL': 15.14, 'UL': 13.95},
            15: {'DL': 33.84, 'UL': 19.73},
            20: {'DL': 44.61, 'UL': 27.35}
        },
        2: {
            5: {'DL': 6.87, 'UL': 3.32},
            10: {'DL': 17.06, 'UL': 6.76},
            15: {'DL': 49.63, 'UL': 10.5},
            20: {'DL': 65.2, 'UL': 14.41}
        },
        3: {
            5: {'DL': 5.41, 'UL': 4.17},
            10: {'DL': 16.89, 'UL': 9.73},
            15: {'DL': 44.29, 'UL': 15.7},
            20: {'DL': 53.95, 'UL': 19.85}
        },
        4: {
            5: {'DL': 8.7, 'UL': 3.32},
            10: {'DL': 17.58, 'UL': 6.76},
            15: {'DL': 51.08, 'UL': 10.47},
            20: {'DL': 66.45, 'UL': 14.38}
        },
        5: {
            5: {'DL': 9.46, 'UL': 1.55},
            10: {'DL': 19.02, 'UL': 3.48},
            15: {'DL': 58.89, 'UL': 5.23},
            20: {'DL': 76.85, 'UL': 7.1}
        },
        6: {
            5: {'DL': 4.74, 'UL': 3.9},
            10: {'DL': 12.32, 'UL': 13.37},
            15: {'DL': 27.74, 'UL': 25.02},
            20: {'DL': 35.48, 'UL': 32.95}
        }
    }

    tdd_config1_tput_lut = {
        0: {
            5: {'DL': 4.25, 'UL': 3.35},
            10: {'DL': 8.38, 'UL': 7.22},
            15: {'DL': 12.41, 'UL': 13.91},
            20: {'DL': 16.27, 'UL': 24.09}
        },
        1: {
            5: {'DL': 7.28, 'UL': 4.61},
            10: {'DL': 14.73, 'UL': 9.69},
            15: {'DL': 21.91, 'UL': 13.86},
            20: {'DL': 27.63, 'UL': 17.18}
        },
        2: {
            5: {'DL': 10.37, 'UL': 2.27},
            10: {'DL': 20.92, 'UL': 4.66},
            15: {'DL': 31.01, 'UL': 7.04},
            20: {'DL': 42.03, 'UL': 9.75}
        },
        3: {
            5: {'DL': 9.25, 'UL': 3.44},
            10: {'DL': 18.38, 'UL': 6.95},
            15: {'DL': 27.59, 'UL': 10.62},
            20: {'DL': 34.85, 'UL': 13.45}
        },
        4: {
            5: {'DL': 10.71, 'UL': 2.26},
            10: {'DL': 21.54, 'UL': 4.67},
            15: {'DL': 31.91, 'UL': 7.2},
            20: {'DL': 43.35, 'UL': 9.74}
        },
        5: {
            5: {'DL': 12.34, 'UL': 1.08},
            10: {'DL': 24.78, 'UL': 2.34},
            15: {'DL': 36.68, 'UL': 3.57},
            20: {'DL': 49.84, 'UL': 4.81}
        },
        6: {
            5: {'DL': 5.76, 'UL': 4.41},
            10: {'DL': 11.68, 'UL': 9.7},
            15: {'DL': 17.34, 'UL': 17.95},
            20: {'DL': 23.5, 'UL': 23.42}
        }
    }
    # yapf: enable

    # Peak throughput lookup table dictionary
    tdd_config_tput_lut_dict = {
        "TDD_CONFIG1": tdd_config1_tput_lut,  # DL 256QAM, UL 64QAM & MAC padding turned OFF
        "TDD_CONFIG2": tdd_config2_tput_lut,  # DL 256QAM, UL 64 QAM ON & MAC padding OFF
        "TDD_CONFIG3": tdd_config3_tput_lut,  # DL 256QAM, UL 64QAM & MAC padding ON
        "TDD_CONFIG4": tdd_config4_tput_lut,  # DL 256QAM, UL 64 QAM OFF & MAC padding ON
    }

    def __init__(
        self, simulator, log, dut, test_config, calibration_table, nr_mode=None
    ):
        """Initializes the simulator for a single-carrier LTE simulation.

        Args:
            simulator: a cellular simulator controller
            log: a logger handle
            dut: a device handler implementing BaseCellularDut
            test_config: test configuration obtained from the config file
            calibration_table: a dictionary containing path losses for
                different bands.

        """

        super().__init__(
            simulator, log, dut, test_config, calibration_table, nr_mode
        )

        self.num_carriers = None

        # Force device to LTE only so that it connects faster
        try:
            if self.nr_mode and "nr" == self.nr_mode:
                self.dut.set_preferred_network_type(
                    BaseCellularDut.PreferredNetworkType.NR_LTE
                )
            else:
                self.dut.set_preferred_network_type(
                    BaseCellularDut.PreferredNetworkType.LTE_ONLY
                )
        except Exception as e:
            # If this fails the test should be able to run anyways, even if it
            # takes longer to find the cell.
            self.log.warning("Setting preferred RAT failed: {}".format(e))

        # Get LTE CA frequency bands setting from the test configuration
        if self.KEY_FREQ_BANDS not in test_config:
            self.log.warning(
                "The key '{}' is not set in the config file. "
                "Setting to null by default.".format(self.KEY_FREQ_BANDS)
            )

        self.freq_bands = test_config.get(self.KEY_FREQ_BANDS, True)

    def setup_simulator(self):
        """Do initial configuration in the simulator."""
        if self.nr_mode and "nr" == self.nr_mode:
            self.log.info("Initializes the callbox to Nr Nsa scenario")
            self.simulator.setup_nr_nsa_scenario()
        else:
            self.log.info("Initializes the callbox to LTE scenario")
            self.simulator.setup_lte_scenario()

    def configure(self, parameters):
        """Configures simulation using a dictionary of parameters.

        Processes LTE configuration parameters.

        Args:
            parameters: a configuration dictionary if there is only one carrier,
                a list if there are multiple cells.
        """
        # If there is a single item, put in a list
        if not isinstance(parameters, list):
            parameters = [parameters]

        # Pass only PCC configs to BaseSimulation
        super().configure(parameters[0])

        new_cell_list = []
        for cell in parameters:
            if LteCellConfig.PARAM_BAND not in cell:
                raise ValueError(
                    "The configuration dictionary must include a key '{}' with "
                    "the required band number.".format(LteCellConfig.PARAM_BAND)
                )

            band = cell[LteCellConfig.PARAM_BAND]

            if isinstance(band, str) and not band.isdigit():
                # If band starts with n then it is an NR band
                if band[0] == "n" and band[1:].isdigit():
                    # If the remaining string is only the band number, add
                    # the cell and continue
                    new_cell_list.append(cell)
                    continue

                ca_class = band[-1].upper()
                band_num = band[:-1]

                if ca_class in ["A", "C"]:
                    # Remove the CA class label and add the cell
                    cell[LteCellConfig.PARAM_BAND] = band_num
                    new_cell_list.append(cell)
                elif ca_class == "B":
                    raise RuntimeError("Class B LTE CA not supported.")
                else:
                    raise ValueError("Invalid band value: " + band)

                # Class C means that there are two contiguous carriers
                if ca_class == "C":
                    new_cell_list.append(dict(cell))
                    bw = int(cell[LteCellConfig.PARAM_BW])
                    dl_earfcn = LteCellConfig.PARAM_DL_EARFCN
                    new_cell_list[-1][dl_earfcn] = (
                        self.LOWEST_DL_CN_DICTIONARY[int(band_num)]
                        + bw * 10
                        - 2
                    )
            else:
                # The band is just a number, so just add it to the list
                new_cell_list.append(cell)

        # Logs new_cell_list for debug
        self.log.info("new cell list: {}".format(new_cell_list))

        self.simulator.set_band_combination(
            [c[LteCellConfig.PARAM_BAND] for c in new_cell_list]
        )

        self.num_carriers = len(new_cell_list)

        # Setup the base stations with the obtain configuration
        self.cell_configs = []
        for i in range(self.num_carriers):
            band = new_cell_list[i][LteCellConfig.PARAM_BAND]
            if isinstance(band, str) and band[0] == "n":
                self.cell_configs.append(NrCellConfig(self.log))
            else:
                self.cell_configs.append(LteCellConfig(self.log))
            self.cell_configs[i].configure(new_cell_list[i])
            self.simulator.configure_bts(self.cell_configs[i], i)

        # Now that the band is set, calibrate the link if necessary
        self.load_pathloss_if_required()

        # This shouldn't be a cell parameter but instead a simulation config
        # Setup LTE RRC status change function and timer for LTE idle test case
        if self.PARAM_RRC_STATUS_CHANGE_TIMER not in parameters[0]:
            self.log.info(
                "The test config does not include the '{}' key. Disabled "
                "by default.".format(self.PARAM_RRC_STATUS_CHANGE_TIMER)
            )
            self.simulator.set_lte_rrc_state_change_timer(False)
        else:
            timer = int(parameters[0][self.PARAM_RRC_STATUS_CHANGE_TIMER])
            self.simulator.set_lte_rrc_state_change_timer(True, timer)
            self.rrc_sc_timer = timer

    def calibrated_downlink_rx_power(self, bts_config, rsrp):
        """LTE simulation overrides this method so that it can convert from
        RSRP to total signal power transmitted from the basestation.

        Args:
            bts_config: the current configuration at the base station
            rsrp: desired rsrp, contained in a key value pair
        """

        power = self.rsrp_to_signal_power(rsrp, bts_config)

        self.log.info(
            "Setting downlink signal level to {} RSRP ({} dBm)".format(
                rsrp, power
            )
        )

        # Use parent method to calculate signal level
        return super().calibrated_downlink_rx_power(bts_config, power)

    def downlink_calibration(self, rat=None, power_units_conversion_func=None):
        """Computes downlink path loss and returns the calibration value.

        See base class implementation for details.

        Args:
            rat: ignored, replaced by 'lteRsrp'
            power_units_conversion_func: ignored, replaced by
                self.rsrp_to_signal_power

        Returns:
            Downlink calibration value and measured DL power. Note that the
            phone only reports RSRP of the primary chain
        """

        return super().downlink_calibration(
            rat="lteDbm", power_units_conversion_func=self.rsrp_to_signal_power
        )

    def rsrp_to_signal_power(self, rsrp, bts_config):
        """Converts rsrp to total band signal power

        RSRP is measured per subcarrier, so total band power needs to be
        multiplied by the number of subcarriers being used.

        Args:
            rsrp: desired rsrp in dBm
            bts_config: a base station configuration object
        Returns:
            Total band signal power in dBm
        """

        bandwidth = bts_config.bandwidth

        if bandwidth == 100:  # This assumes 273 RBs. TODO: b/229163022
            power = rsrp + 35.15
        elif bandwidth == 20:  # 100 RBs
            power = rsrp + 30.79
        elif bandwidth == 15:  # 75 RBs
            power = rsrp + 29.54
        elif bandwidth == 10:  # 50 RBs
            power = rsrp + 27.78
        elif bandwidth == 5:  # 25 RBs
            power = rsrp + 24.77
        elif bandwidth == 3:  # 15 RBs
            power = rsrp + 22.55
        elif bandwidth == 1.4:  # 6 RBs
            power = rsrp + 18.57
        else:
            raise ValueError("Invalid bandwidth value.")

        return power

    def maximum_downlink_throughput(self):
        """Calculates maximum achievable downlink throughput in the current
            simulation state.

        Returns:
            Maximum throughput in mbps.

        """
        return sum(
            self.bts_maximum_downlink_throughtput(self.cell_configs[bts_index])
            for bts_index in range(self.num_carriers)
        )

    def bts_maximum_downlink_throughtput(self, bts_config):
        """Calculates maximum achievable downlink throughput for a single
        base station from its configuration object.

        Args:
            bts_config: a base station configuration object.

        Returns:
            Maximum throughput in mbps.

        """
        if bts_config.mimo_mode == MimoMode.MIMO_1x1:
            streams = 1
        elif bts_config.mimo_mode == MimoMode.MIMO_2x2:
            streams = 2
        elif bts_config.mimo_mode == MimoMode.MIMO_4x4:
            streams = 4
        else:
            raise ValueError(
                "Unable to calculate maximum downlink throughput "
                "because the MIMO mode has not been set."
            )

        bandwidth = bts_config.bandwidth
        rb_ratio = bts_config.dl_rbs / TOTAL_RBS_DICTIONARY[bandwidth]
        mcs = bts_config.dl_mcs

        max_rate_per_stream = None

        tdd_subframe_config = bts_config.dlul_config
        duplex_mode = bts_config.get_duplex_mode()

        if duplex_mode == DuplexMode.TDD:
            if bts_config.dl_256_qam_enabled:
                if mcs == 27:
                    if bts_config.mac_padding:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            "TDD_CONFIG3"
                        ][tdd_subframe_config][bandwidth]["DL"]
                    else:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            "TDD_CONFIG2"
                        ][tdd_subframe_config][bandwidth]["DL"]
            else:
                if mcs == 28:
                    if bts_config.mac_padding:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            "TDD_CONFIG4"
                        ][tdd_subframe_config][bandwidth]["DL"]
                    else:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            "TDD_CONFIG1"
                        ][tdd_subframe_config][bandwidth]["DL"]

        elif duplex_mode == DuplexMode.FDD:
            if (
                not bts_config.dl_256_qam_enabled
                and bts_config.mac_padding
                and mcs == 28
            ):
                max_rate_per_stream = {
                    3: 9.96,
                    5: 17.0,
                    10: 34.7,
                    15: 52.7,
                    20: 72.2,
                }.get(bandwidth, None)
            if (
                not bts_config.dl_256_qam_enabled
                and bts_config.mac_padding
                and mcs == 27
            ):
                max_rate_per_stream = {
                    1.4: 2.94,
                }.get(bandwidth, None)
            elif (
                not bts_config.dl_256_qam_enabled
                and not bts_config.mac_padding
                and mcs == 27
            ):
                max_rate_per_stream = {
                    1.4: 2.87,
                    3: 7.7,
                    5: 14.4,
                    10: 28.7,
                    15: 42.3,
                    20: 57.7,
                }.get(bandwidth, None)
            elif (
                bts_config.dl_256_qam_enabled
                and bts_config.mac_padding
                and mcs == 27
            ):
                max_rate_per_stream = {
                    3: 13.2,
                    5: 22.9,
                    10: 46.3,
                    15: 72.2,
                    20: 93.9,
                }.get(bandwidth, None)
            elif (
                bts_config.dl_256_qam_enabled
                and bts_config.mac_padding
                and mcs == 26
            ):
                max_rate_per_stream = {
                    1.4: 3.96,
                }.get(bandwidth, None)
            elif (
                bts_config.dl_256_qam_enabled
                and not bts_config.mac_padding
                and mcs == 27
            ):
                max_rate_per_stream = {
                    3: 11.3,
                    5: 19.8,
                    10: 44.1,
                    15: 68.1,
                    20: 88.4,
                }.get(bandwidth, None)
            elif (
                bts_config.dl_256_qam_enabled
                and not bts_config.mac_padding
                and mcs == 26
            ):
                max_rate_per_stream = {
                    1.4: 3.96,
                }.get(bandwidth, None)

        if not max_rate_per_stream:
            raise NotImplementedError(
                "The calculation for MAC padding = {} "
                "and mcs = {} is not implemented.".format(
                    "FULLALLOCATION" if bts_config.mac_padding else "OFF", mcs
                )
            )

        return max_rate_per_stream * streams * rb_ratio

    def maximum_uplink_throughput(self):
        """Calculates maximum achievable uplink throughput in the current
            simulation state.

        Returns:
            Maximum throughput in mbps.

        """

        return self.bts_maximum_uplink_throughtput(self.cell_configs[0])

    def bts_maximum_uplink_throughtput(self, bts_config):
        """Calculates maximum achievable uplink throughput for the selected
        basestation from its configuration object.

        Args:
            bts_config: an LTE base station configuration object.

        Returns:
            Maximum throughput in mbps.

        """

        bandwidth = bts_config.bandwidth
        rb_ratio = bts_config.ul_rbs / TOTAL_RBS_DICTIONARY[bandwidth]
        mcs = bts_config.ul_mcs

        max_rate_per_stream = None

        tdd_subframe_config = bts_config.dlul_config
        duplex_mode = bts_config.get_duplex_mode()

        if duplex_mode == DuplexMode.TDD:
            if bts_config.ul_64_qam_enabled:
                if mcs == 28:
                    if bts_config.mac_padding:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            "TDD_CONFIG3"
                        ][tdd_subframe_config][bandwidth]["UL"]
                    else:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            "TDD_CONFIG2"
                        ][tdd_subframe_config][bandwidth]["UL"]
            else:
                if mcs == 23:
                    if bts_config.mac_padding:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            "TDD_CONFIG4"
                        ][tdd_subframe_config][bandwidth]["UL"]
                    else:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            "TDD_CONFIG1"
                        ][tdd_subframe_config][bandwidth]["UL"]

        elif duplex_mode == DuplexMode.FDD:
            if mcs == 23 and not bts_config.ul_64_qam_enabled:
                max_rate_per_stream = {
                    1.4: 2.85,
                    3: 7.18,
                    5: 12.1,
                    10: 24.5,
                    15: 36.5,
                    20: 49.1,
                }.get(bandwidth, None)
            elif mcs == 28 and bts_config.ul_64_qam_enabled:
                max_rate_per_stream = {
                    1.4: 4.2,
                    3: 10.5,
                    5: 17.2,
                    10: 35.3,
                    15: 53.0,
                    20: 72.6,
                }.get(bandwidth, None)

        if not max_rate_per_stream:
            raise NotImplementedError(
                "The calculation fir mcs = {} is not implemented.".format(
                    "FULLALLOCATION" if bts_config.mac_padding else "OFF", mcs
                )
            )

        return max_rate_per_stream * rb_ratio

    def calibrate(self, band):
        """Calculates UL and DL path loss if it wasn't done before

        Before running the base class implementation, configure the base station
        to only use one downlink antenna with maximum bandwidth.

        Args:
            band: the band that is currently being calibrated.
        """

        # Save initial values in a configuration object so they can be restored
        restore_config = LteCellConfig(self.log)
        restore_config.mimo_mode = self.cell_configs[0].mimo_mode
        restore_config.transmission_mode = self.cell_configs[
            0
        ].transmission_mode
        restore_config.bandwidth = self.cell_configs[0].bandwidth

        # Set up a temporary calibration configuration.
        temporary_config = LteCellConfig(self.log)
        temporary_config.mimo_mode = MimoMode.MIMO_1x1
        temporary_config.transmission_mode = TransmissionMode.TM1
        temporary_config.bandwidth = max(
            self.allowed_bandwidth_dictionary[int(band)]
        )
        self.simulator.configure_bts(temporary_config)
        self.cell_configs[0].incorporate(temporary_config)

        super().calibrate(band)

        # Restore values as they were before changing them for calibration.
        self.simulator.configure_bts(restore_config)
        self.cell_configs[0].incorporate(restore_config)

    def start_traffic_for_calibration(self):
        """If MAC padding is enabled, there is no need to start IP traffic."""
        if not self.cell_configs[0].mac_padding:
            super().start_traffic_for_calibration()

    def stop_traffic_for_calibration(self):
        """If MAC padding is enabled, IP traffic wasn't started."""
        if not self.cell_configs[0].mac_padding:
            super().stop_traffic_for_calibration()

    def get_measured_ul_power(self, samples=5, wait_after_sample=3):
        """Calculates UL power using measurements from the callbox and the
        calibration data.

        Args:
            samples: the numble of samples to average
            wait_after_sample: time in seconds to wait in between samples

        Returns:
            the ul power at the UE antenna ports in dBs
        """
        ul_power_sum = 0
        samples_left = samples

        while samples_left > 0:
            ul_power_sum += self.simulator.get_measured_pusch_power()
            samples_left -= 1
            time.sleep(wait_after_sample)

        # Got enough samples, return calibrated average
        if self.dl_path_loss:
            return ul_power_sum / samples + self.ul_path_loss
        else:
            self.log.warning(
                "No uplink calibration data. Returning "
                "uncalibrated values as measured by the "
                "callbox."
            )
            return ul_power_sum / samples

    def start(self):
        """Set the signal level for the secondary carriers, as the base class
        implementation of this method will only set up downlink power for the
        primary carrier component.

        After that, attaches the secondary carriers."""

        super().start()

        if self.num_carriers > 1:
            if self.sim_dl_power:
                self.log.info("Setting DL power for secondary carriers.")

                for bts_index in range(1, self.num_carriers):
                    new_config = LteCellConfig(self.log)
                    new_config.output_power = self.calibrated_downlink_rx_power(
                        self.cell_configs[bts_index], self.sim_dl_power
                    )
                    self.simulator.configure_bts(new_config, bts_index)
                    self.cell_configs[bts_index].incorporate(new_config)

            self.simulator.lte_attach_secondary_carriers(self.freq_bands)

    def send_sms(self, message):
        """Sends an SMS message to the DUT.

        Args:
            message: the SMS message to send.
        """
        self.simulator.send_sms(message)
