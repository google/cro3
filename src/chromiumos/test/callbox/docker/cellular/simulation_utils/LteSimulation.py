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


class TransmissionMode(Enum):
    """ Transmission modes for LTE (e.g., TM1, TM4, ...) """
    TM1 = "TM1"
    TM2 = "TM2"
    TM3 = "TM3"
    TM4 = "TM4"
    TM7 = "TM7"
    TM8 = "TM8"
    TM9 = "TM9"


class MimoMode(Enum):
    """ Mimo modes """
    MIMO_1x1 = "1x1"
    MIMO_2x2 = "2x2"
    MIMO_4x4 = "4x4"


class SchedulingMode(Enum):
    """ Traffic scheduling modes (e.g., STATIC, DYNAMIC) """
    DYNAMIC = "DYNAMIC"
    STATIC = "STATIC"


class DuplexMode(Enum):
    """ DL/UL Duplex mode """
    FDD = "FDD"
    TDD = "TDD"


class ModulationType(Enum):
    """DL/UL Modulation order."""
    QPSK = 'QPSK'
    Q16 = '16QAM'
    Q64 = '64QAM'
    Q256 = '256QAM'


class LteSimulation(BaseSimulation):
    """ Single-carrier LTE simulation. """

    # Simulation config keywords contained in the test name
    PARAM_FRAME_CONFIG = "tddconfig"
    PARAM_BW = "bw"
    PARAM_SCHEDULING = "scheduling"
    PARAM_SCHEDULING_STATIC = "static"
    PARAM_SCHEDULING_DYNAMIC = "dynamic"
    PARAM_PATTERN = "pattern"
    PARAM_TM = "tm"
    PARAM_UL_PW = 'pul'
    PARAM_DL_PW = 'pdl'
    PARAM_BAND = "band"
    PARAM_MIMO = "mimo"
    PARAM_DL_MCS = 'dlmcs'
    PARAM_UL_MCS = 'ulmcs'
    PARAM_SSF = 'ssf'
    PARAM_CFI = 'cfi'
    PARAM_PAGING = 'paging'
    PARAM_PHICH = 'phich'
    PARAM_RRC_STATUS_CHANGE_TIMER = "rrcstatuschangetimer"
    PARAM_DRX = 'drx'

    # Test config keywords
    KEY_TBS_PATTERN = "tbs_pattern_on"
    KEY_DL_256_QAM = "256_qam_dl"
    KEY_UL_64_QAM = "64_qam_ul"

    # Units in which signal level is defined in DOWNLINK_SIGNAL_LEVEL_DICTIONARY
    DOWNLINK_SIGNAL_LEVEL_UNITS = "RSRP"

    # RSRP signal levels thresholds taken from cellular_capability_3gpp.cc
    DOWNLINK_SIGNAL_LEVEL_DICTIONARY = {
        'excellent': -88,
        'high': -98,
        'medium': -108,
        'weak': -118,
        'disconnected': -170
    }

    # Transmitted output power for the phone (dBm)
    UPLINK_SIGNAL_LEVEL_DICTIONARY = {
        'max': 24,
        'high': 13,
        'medium': 3,
        'low': -20
    }

    # Bandwidth [MHz] to total RBs mapping
    total_rbs_dictionary = {20: 100, 15: 75, 10: 50, 5: 25, 3: 15, 1.4: 6}

    # Bandwidth [MHz] to RB group size
    rbg_dictionary = {20: 4, 15: 4, 10: 3, 5: 2, 3: 2, 1.4: 1}

    # Bandwidth [MHz] to minimum number of DL RBs that can be assigned to a UE
    min_dl_rbs_dictionary = {20: 16, 15: 12, 10: 9, 5: 4, 3: 4, 1.4: 2}

    # Bandwidth [MHz] to minimum number of UL RBs that can be assigned to a UE
    min_ul_rbs_dictionary = {20: 8, 15: 6, 10: 4, 5: 2, 3: 2, 1.4: 1}

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
        255: [20]
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
        'TDD_CONFIG1':
        tdd_config1_tput_lut,  # DL 256QAM, UL 64QAM & TBS turned OFF
        'TDD_CONFIG2':
        tdd_config2_tput_lut,  # DL 256QAM, UL 64 QAM turned ON & TBS OFF
        'TDD_CONFIG3':
        tdd_config3_tput_lut,  # DL 256QAM, UL 64QAM & TBS turned ON
        'TDD_CONFIG4':
        tdd_config4_tput_lut  # DL 256QAM, UL 64 QAM turned OFF & TBS ON
    }

    class BtsConfig(BaseSimulation.BtsConfig):
        """ Extension of the BaseBtsConfig to implement parameters that are
         exclusive to LTE.

        Attributes:
            band: an integer indicating the required band number.
            dlul_config: an integer indicating the TDD config number.
            ssf_config: an integer indicating the Special Sub-Frame config.
            bandwidth: a float indicating the required channel bandwidth.
            mimo_mode: an instance of LteSimulation.MimoMode indicating the
                required MIMO mode for the downlink signal.
            transmission_mode: an instance of LteSimulation.TransmissionMode
                indicating the required TM.
            scheduling_mode: an instance of LteSimulation.SchedulingMode
                indicating whether to use Static or Dynamic scheduling.
            dl_rbs: an integer indicating the number of downlink RBs
            ul_rbs: an integer indicating the number of uplink RBs
            dl_mcs: an integer indicating the MCS for the downlink signal
            ul_mcs: an integer indicating the MCS for the uplink signal
            dl_modulation_order: a string indicating a DL modulation scheme
            ul_modulation_order: a string indicating an UL modulation scheme
            tbs_pattern_on: a boolean indicating whether full allocation mode
                should be used or not
            dl_channel: an integer indicating the downlink channel number
            cfi: an integer indicating the Control Format Indicator
            paging_cycle: an integer indicating the paging cycle duration in
                milliseconds
            phich: a string indicating the PHICH group size parameter
            drx_connected_mode: a boolean indicating whether cDRX mode is
                on or off
            drx_on_duration_timer: number of PDCCH subframes representing
                DRX on duration
            drx_inactivity_timer: number of PDCCH subframes to wait before
                entering DRX mode
            drx_retransmission_timer: number of consecutive PDCCH subframes
                to wait for retransmission
            drx_long_cycle: number of subframes representing one long DRX cycle.
                One cycle consists of DRX sleep + DRX on duration
            drx_long_cycle_offset: number representing offset in range
                0 to drx_long_cycle - 1
        """

        def __init__(self):
            """ Initialize the base station config by setting all its
            parameters to None. """
            super(LteSimulation.BtsConfig, self).__init__()
            self.band = None
            self.dlul_config = None
            self.ssf_config = None
            self.bandwidth = None
            self.mimo_mode = None
            self.transmission_mode = None
            self.scheduling_mode = None
            self.dl_rbs = None
            self.ul_rbs = None
            self.dl_mcs = None
            self.ul_mcs = None
            self.dl_modulation_order = None
            self.ul_modulation_order = None
            self.tbs_pattern_on = None
            self.dl_channel = None
            self.cfi = None
            self.paging_cycle = None
            self.phich = None
            self.drx_connected_mode = None
            self.drx_on_duration_timer = None
            self.drx_inactivity_timer = None
            self.drx_retransmission_timer = None
            self.drx_long_cycle = None
            self.drx_long_cycle_offset = None

    def __init__(self, simulator, log, dut, test_config, calibration_table):
        """ Initializes the simulator for a single-carrier LTE simulation.

        Loads a simple LTE simulation environment with 1 basestation.

        Args:
            simulator: a cellular simulator controller
            log: a logger handle
            dut: a device handler implementing BaseCellularDut
            test_config: test configuration obtained from the config file
            calibration_table: a dictionary containing path losses for
                different bands.

        """

        super(LteSimulation, self).__init__(simulator, log, dut, test_config,
                                            calibration_table)

        self.dut.set_preferred_network_type(
            BaseCellularDut.PreferredNetworkType.LTE_ONLY)

        # Get TBS pattern setting from the test configuration
        if self.KEY_TBS_PATTERN not in test_config:
            self.log.warning("The key '{}' is not set in the config file. "
                             "Setting to true by default.".format(
                                 self.KEY_TBS_PATTERN))
        self.primary_config.tbs_pattern_on = test_config.get(
            self.KEY_TBS_PATTERN, True)

        # Get the 256-QAM setting from the test configuration
        if self.KEY_DL_256_QAM not in test_config:
            self.log.warning("The key '{}' is not set in the config file. "
                             "Setting to false by default.".format(
                                 self.KEY_DL_256_QAM))

        self.dl_256_qam = test_config.get(self.KEY_DL_256_QAM, False)

        if self.dl_256_qam:
            if not self.simulator.LTE_SUPPORTS_DL_256QAM:
                self.log.warning("The key '{}' is set to true but the "
                                 "simulator doesn't support that modulation "
                                 "order.".format(self.KEY_DL_256_QAM))
                self.dl_256_qam = False
            else:
                self.primary_config.dl_modulation_order = ModulationType.Q256

        else:
            self.log.warning(
                'dl modulation 256QAM is not specified in config, '
                'setting to default value 64QAM')
            self.primary_config.dl_modulation_order = ModulationType.Q64
        # Get the 64-QAM setting from the test configuration
        if self.KEY_UL_64_QAM not in test_config:
            self.log.warning("The key '{}' is not set in the config file. "
                             "Setting to false by default.".format(
                                 self.KEY_UL_64_QAM))

        self.ul_64_qam = test_config.get(self.KEY_UL_64_QAM, False)

        if self.ul_64_qam:
            if not self.simulator.LTE_SUPPORTS_UL_64QAM:
                self.log.warning("The key '{}' is set to true but the "
                                 "simulator doesn't support that modulation "
                                 "order.".format(self.KEY_UL_64_QAM))
                self.ul_64_qam = False
            else:
                self.primary_config.ul_modulation_order = ModulationType.Q64
        else:
            self.log.warning('ul modulation 64QAM is not specified in config, '
                             'setting to default value 16QAM')
            self.primary_config.ul_modulation_order = ModulationType.Q16

        self.simulator.configure_bts(self.primary_config)

    def setup_simulator(self):
        """ Do initial configuration in the simulator. """
        self.simulator.setup_lte_scenario()

    def parse_parameters(self, parameters):
        """ Configs an LTE simulation using a list of parameters.

        Calls the parent method first, then consumes parameters specific to LTE.

        Args:
            parameters: list of parameters
        """

        # Instantiate a new configuration object
        new_config = self.BtsConfig()

        # Setup band

        values = self.consume_parameter(parameters, self.PARAM_BAND, 1)

        if not values:
            raise ValueError(
                "The test name needs to include parameter '{}' followed by "
                "the required band number.".format(self.PARAM_BAND))

        new_config.band = values[1]

        # Set TDD-only configs
        if self.get_duplex_mode(new_config.band) == DuplexMode.TDD:

            # Sub-frame DL/UL config
            values = self.consume_parameter(parameters,
                                            self.PARAM_FRAME_CONFIG, 1)
            if not values:
                raise ValueError(
                    "When a TDD band is selected the frame "
                    "structure has to be indicated with the '{}' "
                    "parameter followed by a number from 0 to 6.".format(
                        self.PARAM_FRAME_CONFIG))

            new_config.dlul_config = int(values[1])

            # Special Sub-Frame configuration
            values = self.consume_parameter(parameters, self.PARAM_SSF, 1)

            if not values:
                self.log.warning(
                    'The {} parameter was not provided. Setting '
                    'Special Sub-Frame config to 6 by default.'.format(
                        self.PARAM_SSF))
                new_config.ssf_config = 6
            else:
                new_config.ssf_config = int(values[1])

        # Setup bandwidth

        values = self.consume_parameter(parameters, self.PARAM_BW, 1)

        if not values:
            raise ValueError(
                "The test name needs to include parameter {} followed by an "
                "int value (to indicate 1.4 MHz use 14).".format(
                    self.PARAM_BW))

        bw = float(values[1])

        if bw == 14:
            bw = 1.4

        new_config.bandwidth = bw

        # Setup mimo mode

        values = self.consume_parameter(parameters, self.PARAM_MIMO, 1)

        if not values:
            raise ValueError(
                "The test name needs to include parameter '{}' followed by the "
                "mimo mode.".format(self.PARAM_MIMO))

        for mimo_mode in MimoMode:
            if values[1] == mimo_mode.value:
                new_config.mimo_mode = mimo_mode
                break
        else:
            raise ValueError("The {} parameter needs to be followed by either "
                             "1x1, 2x2 or 4x4.".format(self.PARAM_MIMO))

        if (new_config.mimo_mode == MimoMode.MIMO_4x4
                and not self.simulator.LTE_SUPPORTS_4X4_MIMO):
            raise ValueError("The test requires 4x4 MIMO, but that is not "
                             "supported by the cellular simulator.")

        # Setup transmission mode

        values = self.consume_parameter(parameters, self.PARAM_TM, 1)

        if not values:
            raise ValueError(
                "The test name needs to include parameter {} followed by an "
                "int value from 1 to 4 indicating transmission mode.".format(
                    self.PARAM_TM))

        for tm in TransmissionMode:
            if values[1] == tm.value[2:]:
                new_config.transmission_mode = tm
                break
        else:
            raise ValueError("The {} parameter needs to be followed by either "
                             "TM1, TM2, TM3, TM4, TM7, TM8 or TM9.".format(
                                 self.PARAM_MIMO))

        # Setup scheduling mode

        values = self.consume_parameter(parameters, self.PARAM_SCHEDULING, 1)

        if not values:
            new_config.scheduling_mode = SchedulingMode.STATIC
            self.log.warning(
                "The test name does not include the '{}' parameter. Setting to "
                "static by default.".format(self.PARAM_SCHEDULING))
        elif values[1] == self.PARAM_SCHEDULING_DYNAMIC:
            new_config.scheduling_mode = SchedulingMode.DYNAMIC
        elif values[1] == self.PARAM_SCHEDULING_STATIC:
            new_config.scheduling_mode = SchedulingMode.STATIC
        else:
            raise ValueError(
                "The test name parameter '{}' has to be followed by either "
                "'dynamic' or 'static'.".format(self.PARAM_SCHEDULING))

        if new_config.scheduling_mode == SchedulingMode.STATIC:

            values = self.consume_parameter(parameters, self.PARAM_PATTERN, 2)

            if not values:
                self.log.warning(
                    "The '{}' parameter was not set, using 100% RBs for both "
                    "DL and UL. To set the percentages of total RBs include "
                    "the '{}' parameter followed by two ints separated by an "
                    "underscore indicating downlink and uplink percentages.".
                    format(self.PARAM_PATTERN, self.PARAM_PATTERN))
                dl_pattern = 100
                ul_pattern = 100
            else:
                dl_pattern = int(values[1])
                ul_pattern = int(values[2])

            if not (0 <= dl_pattern <= 100 and 0 <= ul_pattern <= 100):
                raise ValueError(
                    "The scheduling pattern parameters need to be two "
                    "positive numbers between 0 and 100.")

            new_config.dl_rbs, new_config.ul_rbs = (
                self.allocation_percentages_to_rbs(
                    new_config.bandwidth, new_config.transmission_mode,
                    dl_pattern, ul_pattern))

            # Look for a DL MCS configuration in the test parameters. If it is
            # not present, use a default value.
            dlmcs = self.consume_parameter(parameters, self.PARAM_DL_MCS, 1)

            if dlmcs:
                new_config.dl_mcs = int(dlmcs[1])
            else:
                self.log.warning(
                    'The test name does not include the {} parameter. Setting '
                    'to the max value by default'.format(self.PARAM_DL_MCS))
                if self.dl_256_qam and new_config.bandwidth == 1.4:
                    new_config.dl_mcs = 26
                elif (not self.dl_256_qam
                      and self.primary_config.tbs_pattern_on
                      and new_config.bandwidth != 1.4):
                    new_config.dl_mcs = 28
                else:
                    new_config.dl_mcs = 27

            # Look for an UL MCS configuration in the test parameters. If it is
            # not present, use a default value.
            ulmcs = self.consume_parameter(parameters, self.PARAM_UL_MCS, 1)

            if ulmcs:
                new_config.ul_mcs = int(ulmcs[1])
            else:
                self.log.warning(
                    'The test name does not include the {} parameter. Setting '
                    'to the max value by default'.format(self.PARAM_UL_MCS))
                if self.ul_64_qam:
                    new_config.ul_mcs = 28
                else:
                    new_config.ul_mcs = 23

        # Configure the simulation for DRX mode

        drx = self.consume_parameter(parameters, self.PARAM_DRX, 5)

        if drx and len(drx) == 6:
            new_config.drx_connected_mode = True
            new_config.drx_on_duration_timer = drx[1]
            new_config.drx_inactivity_timer = drx[2]
            new_config.drx_retransmission_timer = drx[3]
            new_config.drx_long_cycle = drx[4]
            try:
                long_cycle = int(drx[4])
                long_cycle_offset = int(drx[5])
                if long_cycle_offset in range(0, long_cycle):
                    new_config.drx_long_cycle_offset = long_cycle_offset
                else:
                    self.log.error(
                        ("The cDRX long cycle offset must be in the "
                         "range 0 to (long cycle  - 1). Setting "
                         "long cycle offset to 0"))
                    new_config.drx_long_cycle_offset = 0

            except ValueError:
                self.log.error(("cDRX long cycle and long cycle offset "
                                "must be integers. Disabling cDRX mode."))
                new_config.drx_connected_mode = False
        else:
            self.log.warning(("DRX mode was not configured properly. "
                              "Please provide the following 5 values: "
                              "1) DRX on duration timer "
                              "2) Inactivity timer "
                              "3) Retransmission timer "
                              "4) Long DRX cycle duration "
                              "5) Long DRX cycle offset "
                              "Example: drx_2_6_16_20_0"))

        # Setup LTE RRC status change function and timer for LTE idle test case
        values = self.consume_parameter(parameters,
                                        self.PARAM_RRC_STATUS_CHANGE_TIMER, 1)
        if not values:
            self.log.info(
                "The test name does not include the '{}' parameter. Disabled "
                "by default.".format(self.PARAM_RRC_STATUS_CHANGE_TIMER))
            self.simulator.set_lte_rrc_state_change_timer(False)
        else:
            timer = int(values[1])
            self.simulator.set_lte_rrc_state_change_timer(True, timer)
            self.rrc_sc_timer = timer

        # Channel Control Indicator
        values = self.consume_parameter(parameters, self.PARAM_CFI, 1)

        if not values:
            self.log.warning('The {} parameter was not provided. Setting '
                             'CFI to BESTEFFORT.'.format(self.PARAM_CFI))
            new_config.cfi = 'BESTEFFORT'
        else:
            new_config.cfi = values[1]

        # PHICH group size
        values = self.consume_parameter(parameters, self.PARAM_PHICH, 1)

        if not values:
            self.log.warning('The {} parameter was not provided. Setting '
                             'PHICH group size to 1 by default.'.format(
                                 self.PARAM_PHICH))
            new_config.phich = '1'
        else:
            if values[1] == '16':
                new_config.phich = '1/6'
            elif values[1] == '12':
                new_config.phich = '1/2'
            elif values[1] in ['1/6', '1/2', '1', '2']:
                new_config.phich = values[1]
            else:
                raise ValueError('The {} parameter can only be followed by 1,'
                                 '2, 1/2 (or 12) and 1/6 (or 16).'.format(
                                     self.PARAM_PHICH))

        # Paging cycle duration
        values = self.consume_parameter(parameters, self.PARAM_PAGING, 1)

        if not values:
            self.log.warning('The {} parameter was not provided. Setting '
                             'paging cycle duration to 1280 ms by '
                             'default.'.format(self.PARAM_PAGING))
            new_config.paging_cycle = 1280
        else:
            try:
                new_config.paging_cycle = int(values[1])
            except ValueError:
                raise ValueError(
                    'The {} parameter has to be followed by the paging cycle '
                    'duration in milliseconds.'.format(self.PARAM_PAGING))

        # Get uplink power

        ul_power = self.get_uplink_power_from_parameters(parameters)

        # Power is not set on the callbox until after the simulation is
        # started. Saving this value in a variable for later
        self.sim_ul_power = ul_power

        # Get downlink power

        dl_power = self.get_downlink_power_from_parameters(parameters)

        # Power is not set on the callbox until after the simulation is
        # started. Saving this value in a variable for later
        self.sim_dl_power = dl_power

        # Setup the base station with the obtained configuration and then save
        # these parameters in the current configuration object
        self.simulator.configure_bts(new_config)
        self.primary_config.incorporate(new_config)

        # Now that the band is set, calibrate the link if necessary
        self.load_pathloss_if_required()

    def downlink_calibration(self, rat=None, power_units_conversion_func=None):
        """ Computes downlink path loss and returns the calibration value.

        See base class implementation for details.

        Args:
            rat: ignored, replaced by 'lteRsrp'
            power_units_conversion_func: ignored, replaced by
                self.rsrp_to_signal_power

        Returns:
            Downlink calibration value and measured DL power. Note that the
            phone only reports RSRP of the primary chain
        """

        return super().downlink_calibration(rat='lteDbm')

    def rsrp_to_signal_power(self, rsrp, bts_config):
        """ Converts rsrp to total band signal power

        RSRP is measured per subcarrier, so total band power needs to be
        multiplied by the number of subcarriers being used.

        Args:
            rsrp: desired rsrp in dBm
            bts_config: a base station configuration object
        Returns:
            Total band signal power in dBm
        """

        bandwidth = bts_config.bandwidth

        if bandwidth == 20:  # 100 RBs
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
        """ Calculates maximum achievable downlink throughput in the current
            simulation state.

        Returns:
            Maximum throughput in mbps.

        """

        return self.bts_maximum_downlink_throughtput(self.primary_config)

    def bts_maximum_downlink_throughtput(self, bts_config):
        """ Calculates maximum achievable downlink throughput for a single
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
            raise ValueError('Unable to calculate maximum downlink throughput '
                             'because the MIMO mode has not been set.')

        bandwidth = bts_config.bandwidth
        rb_ratio = bts_config.dl_rbs / self.total_rbs_dictionary[bandwidth]
        mcs = bts_config.dl_mcs

        max_rate_per_stream = None

        tdd_subframe_config = bts_config.dlul_config
        duplex_mode = self.get_duplex_mode(bts_config.band)

        if duplex_mode == DuplexMode.TDD:
            if self.dl_256_qam:
                if mcs == 27:
                    if bts_config.tbs_pattern_on:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            'TDD_CONFIG3'][tdd_subframe_config][bandwidth][
                                'DL']
                    else:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            'TDD_CONFIG2'][tdd_subframe_config][bandwidth][
                                'DL']
            else:
                if mcs == 28:
                    if bts_config.tbs_pattern_on:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            'TDD_CONFIG4'][tdd_subframe_config][bandwidth][
                                'DL']
                    else:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            'TDD_CONFIG1'][tdd_subframe_config][bandwidth][
                                'DL']

        elif duplex_mode == DuplexMode.FDD:
            if (not self.dl_256_qam and bts_config.tbs_pattern_on
                    and mcs == 28):
                max_rate_per_stream = {
                    3: 9.96,
                    5: 17.0,
                    10: 34.7,
                    15: 52.7,
                    20: 72.2
                }.get(bandwidth, None)
            if (not self.dl_256_qam and bts_config.tbs_pattern_on
                    and mcs == 27):
                max_rate_per_stream = {
                    1.4: 2.94,
                }.get(bandwidth, None)
            elif (not self.dl_256_qam and not bts_config.tbs_pattern_on
                  and mcs == 27):
                max_rate_per_stream = {
                    1.4: 2.87,
                    3: 7.7,
                    5: 14.4,
                    10: 28.7,
                    15: 42.3,
                    20: 57.7
                }.get(bandwidth, None)
            elif self.dl_256_qam and bts_config.tbs_pattern_on and mcs == 27:
                max_rate_per_stream = {
                    3: 13.2,
                    5: 22.9,
                    10: 46.3,
                    15: 72.2,
                    20: 93.9
                }.get(bandwidth, None)
            elif self.dl_256_qam and bts_config.tbs_pattern_on and mcs == 26:
                max_rate_per_stream = {
                    1.4: 3.96,
                }.get(bandwidth, None)
            elif (self.dl_256_qam and not bts_config.tbs_pattern_on
                  and mcs == 27):
                max_rate_per_stream = {
                    3: 11.3,
                    5: 19.8,
                    10: 44.1,
                    15: 68.1,
                    20: 88.4
                }.get(bandwidth, None)
            elif (self.dl_256_qam and not bts_config.tbs_pattern_on
                  and mcs == 26):
                max_rate_per_stream = {
                    1.4: 3.96,
                }.get(bandwidth, None)

        if not max_rate_per_stream:
            raise NotImplementedError(
                "The calculation for tbs pattern = {} "
                "and mcs = {} is not implemented.".format(
                    "FULLALLOCATION" if bts_config.tbs_pattern_on else "OFF",
                    mcs))

        return max_rate_per_stream * streams * rb_ratio

    def maximum_uplink_throughput(self):
        """ Calculates maximum achievable uplink throughput in the current
            simulation state.

        Returns:
            Maximum throughput in mbps.

        """

        return self.bts_maximum_uplink_throughtput(self.primary_config)

    def bts_maximum_uplink_throughtput(self, bts_config):
        """ Calculates maximum achievable uplink throughput for the selected
        basestation from its configuration object.

        Args:
            bts_config: an LTE base station configuration object.

        Returns:
            Maximum throughput in mbps.

        """

        bandwidth = bts_config.bandwidth
        rb_ratio = bts_config.ul_rbs / self.total_rbs_dictionary[bandwidth]
        mcs = bts_config.ul_mcs

        max_rate_per_stream = None

        tdd_subframe_config = bts_config.dlul_config
        duplex_mode = self.get_duplex_mode(bts_config.band)

        if duplex_mode == DuplexMode.TDD:
            if self.ul_64_qam:
                if mcs == 28:
                    if bts_config.tbs_pattern_on:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            'TDD_CONFIG3'][tdd_subframe_config][bandwidth][
                                'UL']
                    else:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            'TDD_CONFIG2'][tdd_subframe_config][bandwidth][
                                'UL']
            else:
                if mcs == 23:
                    if bts_config.tbs_pattern_on:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            'TDD_CONFIG4'][tdd_subframe_config][bandwidth][
                                'UL']
                    else:
                        max_rate_per_stream = self.tdd_config_tput_lut_dict[
                            'TDD_CONFIG1'][tdd_subframe_config][bandwidth][
                                'UL']

        elif duplex_mode == DuplexMode.FDD:
            if mcs == 23 and not self.ul_64_qam:
                max_rate_per_stream = {
                    1.4: 2.85,
                    3: 7.18,
                    5: 12.1,
                    10: 24.5,
                    15: 36.5,
                    20: 49.1
                }.get(bandwidth, None)
            elif mcs == 28 and self.ul_64_qam:
                max_rate_per_stream = {
                    1.4: 4.2,
                    3: 10.5,
                    5: 17.2,
                    10: 35.3,
                    15: 53.0,
                    20: 72.6
                }.get(bandwidth, None)

        if not max_rate_per_stream:
            raise NotImplementedError(
                "The calculation fir mcs = {} is not implemented.".format(
                    "FULLALLOCATION" if bts_config.tbs_pattern_on else "OFF",
                    mcs))

        return max_rate_per_stream * rb_ratio

    def allocation_percentages_to_rbs(self, bw, tm, dl, ul):
        """ Converts usage percentages to number of DL/UL RBs

        Because not any number of DL/UL RBs can be obtained for a certain
        bandwidth, this function calculates the number of RBs that most
        closely matches the desired DL/UL percentages.

        Args:
            bw: the bandwidth for the which the RB configuration is requested
            tm: the transmission in which the base station will be operating
            dl: desired percentage of downlink RBs
            ul: desired percentage of uplink RBs
        Returns:
            a tuple indicating the number of downlink and uplink RBs
        """

        # Validate the arguments
        if (not 0 <= dl <= 100) or (not 0 <= ul <= 100):
            raise ValueError("The percentage of DL and UL RBs have to be two "
                             "positive between 0 and 100.")

        # Get min and max values from tables
        max_rbs = self.total_rbs_dictionary[bw]
        min_dl_rbs = self.min_dl_rbs_dictionary[bw]
        min_ul_rbs = self.min_ul_rbs_dictionary[bw]

        def percentage_to_amount(min_val, max_val, percentage):
            """ Returns the integer between min_val and max_val that is closest
            to percentage/100*max_val
            """

            # Calculate the value that corresponds to the required percentage.
            closest_int = round(max_val * percentage / 100)
            # Cannot be less than min_val
            closest_int = max(closest_int, min_val)
            # RBs cannot be more than max_rbs
            closest_int = min(closest_int, max_val)

            return closest_int

        # Calculate the number of DL RBs

        # Get the number of DL RBs that corresponds to
        #  the required percentage.
        desired_dl_rbs = percentage_to_amount(min_val=min_dl_rbs,
                                              max_val=max_rbs,
                                              percentage=dl)

        if tm == TransmissionMode.TM3 or tm == TransmissionMode.TM4:

            # For TM3 and TM4 the number of DL RBs needs to be max_rbs or a
            # multiple of the RBG size

            if desired_dl_rbs == max_rbs:
                dl_rbs = max_rbs
            else:
                dl_rbs = (math.ceil(desired_dl_rbs / self.rbg_dictionary[bw]) *
                          self.rbg_dictionary[bw])

        else:
            # The other TMs allow any number of RBs between 1 and max_rbs
            dl_rbs = desired_dl_rbs

        # Calculate the number of UL RBs

        # Get the number of UL RBs that corresponds
        # to the required percentage
        desired_ul_rbs = percentage_to_amount(min_val=min_ul_rbs,
                                              max_val=max_rbs,
                                              percentage=ul)

        # Create a list of all possible UL RBs assignment
        # The standard allows any number that can be written as
        # 2**a * 3**b * 5**c for any combination of a, b and c.

        def pow_range(max_value, base):
            """ Returns a range of all possible powers of base under
              the given max_value.
          """
            return range(int(math.ceil(math.log(max_value, base))))

        possible_ul_rbs = [
            2**a * 3**b * 5**c for a in pow_range(max_rbs, 2)
            for b in pow_range(max_rbs, 3)
            for c in pow_range(max_rbs, 5)
            if 2**a * 3**b * 5**c <= max_rbs] # yapf: disable

        # Find the value in the list that is closest to desired_ul_rbs
        differences = [abs(rbs - desired_ul_rbs) for rbs in possible_ul_rbs]
        ul_rbs = possible_ul_rbs[differences.index(min(differences))]

        # Report what are the obtained RB percentages
        self.log.info("Requested a {}% / {}% RB allocation. Closest possible "
                      "percentages are {}% / {}%.".format(
                          dl, ul, round(100 * dl_rbs / max_rbs),
                          round(100 * ul_rbs / max_rbs)))

        return dl_rbs, ul_rbs

    def calibrate(self, band):
        """ Calculates UL and DL path loss if it wasn't done before

        Before running the base class implementation, configure the base station
        to only use one downlink antenna with maximum bandwidth.

        Args:
            band: the band that is currently being calibrated.
        """

        # Save initial values in a configuration object so they can be restored
        restore_config = self.BtsConfig()
        restore_config.mimo_mode = self.primary_config.mimo_mode
        restore_config.transmission_mode = self.primary_config.transmission_mode
        restore_config.bandwidth = self.primary_config.bandwidth

        # Set up a temporary calibration configuration.
        temporary_config = self.BtsConfig()
        temporary_config.mimo_mode = MimoMode.MIMO_1x1
        temporary_config.transmission_mode = TransmissionMode.TM1
        temporary_config.bandwidth = max(
            self.allowed_bandwidth_dictionary[int(band)])
        self.simulator.configure_bts(temporary_config)
        self.primary_config.incorporate(temporary_config)

        super().calibrate(band)

        # Restore values as they were before changing them for calibration.
        self.simulator.configure_bts(restore_config)
        self.primary_config.incorporate(restore_config)

    def start_traffic_for_calibration(self):
        """
            If TBS pattern is set to full allocation, there is no need to start
            IP traffic.
        """
        if not self.primary_config.tbs_pattern_on:
            super().start_traffic_for_calibration()

    def stop_traffic_for_calibration(self):
        """
            If TBS pattern is set to full allocation, IP traffic wasn't started
        """
        if not self.primary_config.tbs_pattern_on:
            super().stop_traffic_for_calibration()

    def get_duplex_mode(self, band):
        """ Determines if the band uses FDD or TDD duplex mode

        Args:
            band: a band number
        Returns:
            an variable of class DuplexMode indicating if band is FDD or TDD
        """

        if 33 <= int(band) <= 46:
            return DuplexMode.TDD
        else:
            return DuplexMode.FDD

    def get_measured_ul_power(self, samples=5, wait_after_sample=3):
        """ Calculates UL power using measurements from the callbox and the
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
            self.log.warning('No uplink calibration data. Returning '
                             'uncalibrated values as measured by the '
                             'callbox.')
            return ul_power_sum / samples

    def send_sms(self, sms_message):
        """ Sets the SMS message for the simulation. """
        self.simulator.send_sms(sms_message)
