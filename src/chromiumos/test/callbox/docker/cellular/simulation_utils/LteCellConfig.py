# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Python module for configuring LTE cells."""

# pylint: disable=banned-string-format-function
# pylint: disable=docstring-leading-whitespace, docstring-section-newline
# pylint: disable=docstring-trailing-quotes, docstring-second-line-blank
# pylint: disable=attribute-defined-outside-init

import math

from cellular.simulation_utils import BaseCellConfig as base_cell
from cellular.simulation_utils import LteSimulation as lte_sim


class LteCellConfig(base_cell.BaseCellConfig):
    """Extension of the BaseBtsConfig to implement parameters that are
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
        dl_256_qam_enabled: a boolean indicating if 256 QAM is enabled
        ul_64_qam_enabled: a boolean indicating if 256 QAM is enabled
        mac_padding: a boolean indicating whether RBs should be allocated
            when there is no user data in static scheduling
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

    PARAM_FRAME_CONFIG = "tddconfig"
    PARAM_BW = "bw"
    PARAM_SCHEDULING = "scheduling"
    PARAM_SCHEDULING_STATIC = "static"
    PARAM_SCHEDULING_DYNAMIC = "dynamic"
    PARAM_PATTERN = "pattern"
    PARAM_TM = "tm"
    PARAM_BAND = "band"
    PARAM_MIMO = "mimo"
    PARAM_DL_MCS = "dlmcs"
    PARAM_UL_MCS = "ulmcs"
    PARAM_SSF = "ssf"
    PARAM_CFI = "cfi"
    PARAM_PAGING = "paging"
    PARAM_PHICH = "phich"
    PARAM_DRX = "drx"
    PARAM_PADDING = "mac_padding"
    PARAM_DL_256_QAM_ENABLED = "256_qam_dl_enabled"
    PARAM_UL_64_QAM_ENABLED = "64_qam_ul_enabled"
    PARAM_DL_EARFCN = "dl_earfcn"

    def __init__(self, log):
        """Initialize the base station config by setting all its
        parameters to None.
        Args:
            log: logger object.
        """
        super().__init__(log)
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
        self.dl_256_qam_enabled = None
        self.ul_64_qam_enabled = None
        self.mac_padding = None
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

    def __str__(self):
        return str(vars(self))

    def configure(self, parameters):
        """Configures an LTE cell using a dictionary of parameters.

        Args:
            parameters: a configuration dictionary
        """
        # Setup band
        if self.PARAM_BAND not in parameters:
            raise ValueError(
                "The configuration dictionary must include a key '{}' with "
                "the required band number.".format(self.PARAM_BAND)
            )

        self.band = parameters[self.PARAM_BAND]

        if self.PARAM_DL_EARFCN not in parameters:
            band = int(self.band)
            channel = (
                int(
                    lte_sim.LteSimulation.LOWEST_DL_CN_DICTIONARY[band]
                    + lte_sim.LteSimulation.LOWEST_DL_CN_DICTIONARY[band + 1]
                )
                / 2
            )
            self.log.warning(
                "Key '{}' was not set. Using center band channel {} by default.".format(
                    self.PARAM_DL_EARFCN, channel
                )
            )
            self.dl_channel = channel
        else:
            self.dl_channel = parameters[self.PARAM_DL_EARFCN]

        # Set TDD-only configs
        if self.get_duplex_mode() == lte_sim.DuplexMode.TDD:

            # Sub-frame DL/UL config
            if self.PARAM_FRAME_CONFIG not in parameters:
                raise ValueError(
                    "When a TDD band is selected the frame "
                    "structure has to be indicated with the '{}' "
                    "key with a value from 0 to 6.".format(
                        self.PARAM_FRAME_CONFIG
                    )
                )

            self.dlul_config = int(parameters[self.PARAM_FRAME_CONFIG])

            # Special Sub-Frame configuration
            if self.PARAM_SSF not in parameters:
                self.log.warning(
                    "The {} parameter was not provided. Setting "
                    "Special Sub-Frame config to 6 by default.".format(
                        self.PARAM_SSF
                    )
                )
                self.ssf_config = 6
            else:
                self.ssf_config = int(parameters[self.PARAM_SSF])

        # Setup bandwidth
        if self.PARAM_BW not in parameters:
            raise ValueError(
                "The config dictionary must include parameter {} with an "
                "int value (to indicate 1.4 MHz use 14).".format(self.PARAM_BW)
            )

        bw = float(parameters[self.PARAM_BW])

        if abs(bw - 14) < 0.00000000001:
            bw = 1.4

        self.bandwidth = bw

        # Setup mimo mode
        if self.PARAM_MIMO not in parameters:
            raise ValueError(
                "The config dictionary must include parameter '{}' with the "
                "mimo mode.".format(self.PARAM_MIMO)
            )

        for mimo_mode in lte_sim.MimoMode:
            if parameters[self.PARAM_MIMO] == mimo_mode.value:
                self.mimo_mode = mimo_mode
                break
        else:
            raise ValueError(
                "The value of {} must be one of the following:"
                "1x1, 2x2 or 4x4.".format(self.PARAM_MIMO)
            )

        # Setup transmission mode
        if self.PARAM_TM not in parameters:
            raise ValueError(
                "The config dictionary must include key {} with an "
                "int value from 1 to 4 indicating transmission mode.".format(
                    self.PARAM_TM
                )
            )

        for tm in lte_sim.TransmissionMode:
            if parameters[self.PARAM_TM] == tm.value[2:]:
                self.transmission_mode = tm
                break
        else:
            raise ValueError(
                "The {} key must have one of the following values:"
                "1, 2, 3, 4, 7, 8 or 9.".format(self.PARAM_TM)
            )

        # Setup scheduling mode
        if self.PARAM_SCHEDULING not in parameters:
            self.scheduling_mode = lte_sim.SchedulingMode.STATIC
            self.log.warning(
                "The test config does not include the '{}' key. Setting to "
                "static by default.".format(self.PARAM_SCHEDULING)
            )
        elif parameters[self.PARAM_SCHEDULING] == self.PARAM_SCHEDULING_DYNAMIC:
            self.scheduling_mode = lte_sim.SchedulingMode.DYNAMIC
        elif parameters[self.PARAM_SCHEDULING] == self.PARAM_SCHEDULING_STATIC:
            self.scheduling_mode = lte_sim.SchedulingMode.STATIC
        else:
            raise ValueError(
                "Key '{}' must have a value of "
                "'dynamic' or 'static'.".format(self.PARAM_SCHEDULING)
            )

        if self.scheduling_mode == lte_sim.SchedulingMode.STATIC:

            if self.PARAM_PADDING not in parameters:
                self.log.warning(
                    "The '{}' parameter was not set. Enabling MAC padding by "
                    "default.".format(self.PARAM_PADDING)
                )
                self.mac_padding = True
            else:
                self.mac_padding = parameters[self.PARAM_PADDING]

            if self.PARAM_PATTERN not in parameters:
                self.log.warning(
                    "The '{}' parameter was not set, using 100% RBs for both "
                    "DL and UL. To set the percentages of total RBs include "
                    "the '{}' key with a list of two ints indicating downlink "
                    "and uplink percentages.".format(
                        self.PARAM_PATTERN, self.PARAM_PATTERN
                    )
                )
                dl_pattern = 100
                ul_pattern = 100
            else:
                dl_pattern = int(parameters[self.PARAM_PATTERN][0])
                ul_pattern = int(parameters[self.PARAM_PATTERN][1])

            if not (0 <= dl_pattern <= 100 and 0 <= ul_pattern <= 100):
                raise ValueError(
                    "The scheduling pattern parameters need to be two "
                    "positive numbers between 0 and 100."
                )

            self.dl_rbs, self.ul_rbs = self.allocation_percentages_to_rbs(
                dl_pattern, ul_pattern
            )

            # Check if 256 QAM is enabled for DL MCS
            if self.PARAM_DL_256_QAM_ENABLED not in parameters:
                self.log.warning(
                    "The key '{}' is not set in the test config. "
                    "Setting to false by default.".format(
                        self.PARAM_DL_256_QAM_ENABLED
                    )
                )

            self.dl_256_qam_enabled = parameters.get(
                self.PARAM_DL_256_QAM_ENABLED, False
            )

            # Look for a DL MCS configuration in the test parameters. If it is
            # not present, use a default value.
            if self.PARAM_DL_MCS in parameters:
                self.dl_mcs = int(parameters[self.PARAM_DL_MCS])
            else:
                self.log.warning(
                    "The test config does not include the {} key. Setting "
                    "to the max value by default".format(self.PARAM_DL_MCS)
                )
                if self.dl_256_qam_enabled and self.bandwidth == 1.4:
                    self.dl_mcs = 26
                elif (
                    not self.dl_256_qam_enabled
                    and self.mac_padding
                    and self.bandwidth != 1.4
                ):
                    self.dl_mcs = 28
                else:
                    self.dl_mcs = 27

            # Check if 64 QAM is enabled for UL MCS
            if self.PARAM_UL_64_QAM_ENABLED not in parameters:
                self.log.warning(
                    "The key '{}' is not set in the config file. "
                    "Setting to false by default.".format(
                        self.PARAM_UL_64_QAM_ENABLED
                    )
                )

            self.ul_64_qam_enabled = parameters.get(
                self.PARAM_UL_64_QAM_ENABLED, False
            )

            # Look for an UL MCS configuration in the test parameters. If it is
            # not present, use a default value.
            if self.PARAM_UL_MCS in parameters:
                self.ul_mcs = int(parameters[self.PARAM_UL_MCS])
            else:
                self.log.warning(
                    "The test config does not include the {} key. Setting "
                    "to the max value by default".format(self.PARAM_UL_MCS)
                )
                if self.ul_64_qam_enabled:
                    self.ul_mcs = 28
                else:
                    self.ul_mcs = 23

        # Configure the simulation for DRX mode
        if (
            self.PARAM_DRX in parameters
            and len(parameters[self.PARAM_DRX]) == 5
        ):
            self.drx_connected_mode = True
            self.drx_on_duration_timer = parameters[self.PARAM_DRX][0]
            self.drx_inactivity_timer = parameters[self.PARAM_DRX][1]
            self.drx_retransmission_timer = parameters[self.PARAM_DRX][2]
            self.drx_long_cycle = parameters[self.PARAM_DRX][3]
            try:
                long_cycle = int(parameters[self.PARAM_DRX][3])
                long_cycle_offset = int(parameters[self.PARAM_DRX][4])
                if long_cycle_offset in range(0, long_cycle):
                    self.drx_long_cycle_offset = long_cycle_offset
                else:
                    self.log.error(
                        (
                            "The cDRX long cycle offset must be in the "
                            "range 0 to (long cycle  - 1). Setting "
                            "long cycle offset to 0"
                        )
                    )
                    self.drx_long_cycle_offset = 0

            except ValueError:
                self.log.error(
                    (
                        "cDRX long cycle and long cycle offset "
                        "must be integers. Disabling cDRX mode."
                    )
                )
                self.drx_connected_mode = False
        else:
            self.log.warning(
                (
                    "DRX mode was not configured properly. "
                    "Please provide a list with the following values: "
                    "1) DRX on duration timer "
                    "2) Inactivity timer "
                    "3) Retransmission timer "
                    "4) Long DRX cycle duration "
                    "5) Long DRX cycle offset "
                    "Example: [2, 6, 16, 20, 0]."
                )
            )

        # Channel Control Indicator
        if self.PARAM_CFI not in parameters:
            self.log.warning(
                "The {} parameter was not provided. Setting "
                "CFI to BESTEFFORT.".format(self.PARAM_CFI)
            )
            self.cfi = "BESTEFFORT"
        else:
            self.cfi = parameters[self.PARAM_CFI]

        # PHICH group size
        if self.PARAM_PHICH not in parameters:
            self.log.warning(
                "The {} parameter was not provided. Setting "
                "PHICH group size to 1 by default.".format(self.PARAM_PHICH)
            )
            self.phich = "1"
        else:
            if parameters[self.PARAM_PHICH] == "16":
                self.phich = "1/6"
            elif parameters[self.PARAM_PHICH] == "12":
                self.phich = "1/2"
            elif parameters[self.PARAM_PHICH] in ["1/6", "1/2", "1", "2"]:
                self.phich = parameters[self.PARAM_PHICH]
            else:
                raise ValueError(
                    "The {} parameter can only be followed by 1,"
                    "2, 1/2 (or 12) and 1/6 (or 16).".format(self.PARAM_PHICH)
                )

        # Paging cycle duration
        if self.PARAM_PAGING not in parameters:
            self.log.warning(
                "The {} parameter was not provided. Setting "
                "paging cycle duration to 1280 ms by "
                "default.".format(self.PARAM_PAGING)
            )
            self.paging_cycle = 1280
        else:
            try:
                self.paging_cycle = int(parameters[self.PARAM_PAGING])
            except ValueError:
                raise ValueError(
                    "The {} key has to be followed by the paging cycle "
                    "duration in milliseconds.".format(self.PARAM_PAGING)
                )

    def get_duplex_mode(self):
        """Determines if the cell uses FDD or TDD duplex mode

        Returns:
          an variable of class DuplexMode indicating if band is FDD or TDD
        """
        if 33 <= int(self.band) <= 46:
            return lte_sim.DuplexMode.TDD
        else:
            return lte_sim.DuplexMode.FDD

    def allocation_percentages_to_rbs(self, dl, ul):
        """Converts usage percentages to number of DL/UL RBs

        Because not any number of DL/UL RBs can be obtained for a certain
        bandwidth, this function calculates the number of RBs that most
        closely matches the desired DL/UL percentages.

        Args:
            dl: desired percentage of downlink RBs
            ul: desired percentage of uplink RBs

        Returns:
            a tuple indicating the number of downlink and uplink RBs
        """

        # Validate the arguments
        if (not 0 <= dl <= 100) or (not 0 <= ul <= 100):
            raise ValueError(
                "The percentage of DL and UL RBs have to be two "
                "positive between 0 and 100."
            )

        # Get min and max values from tables
        max_rbs = lte_sim.TOTAL_RBS_DICTIONARY[self.bandwidth]
        min_dl_rbs = lte_sim.MIN_DL_RBS_DICTIONARY[self.bandwidth]
        min_ul_rbs = lte_sim.MIN_UL_RBS_DICTIONARY[self.bandwidth]

        def percentage_to_amount(min_val, max_val, percentage):
            """Returns the integer between min_val and max_val that is closest
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
        desired_dl_rbs = percentage_to_amount(
            min_val=min_dl_rbs, max_val=max_rbs, percentage=dl
        )

        if (
            self.transmission_mode == lte_sim.TransmissionMode.TM3
            or self.transmission_mode == lte_sim.TransmissionMode.TM4
        ):

            # For TM3 and TM4 the number of DL RBs needs to be max_rbs or a
            # multiple of the RBG size

            if desired_dl_rbs == max_rbs:
                dl_rbs = max_rbs
            else:
                dl_rbs = (
                    math.ceil(
                        desired_dl_rbs / lte_sim.RBG_DICTIONARY[self.bandwidth]
                    )
                    * lte_sim.RBG_DICTIONARY[self.bandwidth]
                )

        else:
            # The other TMs allow any number of RBs between 1 and max_rbs
            dl_rbs = desired_dl_rbs

        # Calculate the number of UL RBs

        # Get the number of UL RBs that corresponds
        # to the required percentage
        desired_ul_rbs = percentage_to_amount(
            min_val=min_ul_rbs, max_val=max_rbs, percentage=ul
        )

        # Create a list of all possible UL RBs assignment
        # The standard allows any number that can be written as
        # 2**a * 3**b * 5**c for any combination of a, b and c.

        def pow_range(max_value, base):
            """Returns a range of all possible powers of base under
            the given max_value.
            """
            return range(  # pylint: disable=W1638
                int(math.ceil(math.log(max_value, base)))
            )

        possible_ul_rbs = [
            2**a * 3**b * 5**c
            for a in pow_range(max_rbs, 2)
            for b in pow_range(max_rbs, 3)
            for c in pow_range(max_rbs, 5)
            if 2**a * 3**b * 5**c <= max_rbs
        ]  # yapf: disable

        # Find the value in the list that is closest to desired_ul_rbs
        differences = [abs(rbs - desired_ul_rbs) for rbs in possible_ul_rbs]
        ul_rbs = possible_ul_rbs[differences.index(min(differences))]

        # Report what are the obtained RB percentages
        self.log.info(
            "Requested a {}% / {}% RB allocation. Closest possible "
            "percentages are {}% / {}%.".format(
                dl,
                ul,
                round(100 * dl_rbs / max_rbs),
                round(100 * ul_rbs / max_rbs),
            )
        )

        return dl_rbs, ul_rbs
