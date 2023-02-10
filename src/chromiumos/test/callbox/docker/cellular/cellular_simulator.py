# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(b/254347891): unify formatting and ignore specific lints in callbox libraries
# pylint: skip-file

from cellular import logger
from cellular import simulation_utils as cellular_lib


class AbstractCellularSimulator:
    """A generic cellular simulator controller class that can be derived to
    implement equipment specific classes and allows the tests to be implemented
    without depending on a singular instrument model.

    This class defines the interface that every cellular simulator controller
    needs to implement and shouldn't be instantiated by itself."""

    # The maximum number of carriers that this simulator can support for LTE
    LTE_MAX_CARRIERS = None

    # The maximum power that the equipment is able to transmit
    MAX_DL_POWER = None

    def __init__(self):
        """Initializes the cellular simulator."""
        self.log = logger.create_tagged_trace_logger("CellularSimulator")
        self.num_carriers = None

    def destroy(self):
        """Sends finalization commands to the cellular equipment and closes
        the connection."""
        raise NotImplementedError()

    def setup_lte_scenario(self):
        """Configures the equipment for an LTE simulation."""
        raise NotImplementedError()

    def set_band_combination(self, bands):
        """Prepares the test equipment for the indicated CA combination.

        Args:
            bands: a list of bands represented as ints or strings
        """
        raise NotImplementedError()

    def configure_bts(self, config, bts_index=0):
        """Commands the equipment to setup a base station with the required
        configuration. This method applies configurations that are common to all
        RATs.

        Args:
            config: a BaseSimulation.BtsConfig object.
            bts_index: the base station number.
        """

        config_vars = vars(config)
        config_dict = {
            key: config_vars[key] for key in config_vars if config_vars[key]
        }
        self.log.info("The config for {} is {}".format(bts_index, config_dict))

        if config.output_power:
            self.set_output_power(bts_index, config.output_power)

        if config.input_power:
            self.set_input_power(bts_index, config.input_power)

        if isinstance(config, cellular_lib.LteCellConfig.LteCellConfig):
            self.configure_lte_bts(config, bts_index)

        if isinstance(config, cellular_lib.NrCellConfig.NrCellConfig):
            self.configure_nr_bts(config, bts_index)

    def configure_lte_bts(self, config, bts_index=0):
        """Commands the equipment to setup an LTE base station with the
        required configuration.

        Args:
            config: an LteSimulation.BtsConfig object.
            bts_index: the base station number.
        """
        if config.band:
            self.set_band(bts_index, config.band)

        if config.dlul_config:
            self.set_tdd_config(bts_index, config.dlul_config)

        if config.ssf_config:
            self.set_ssf_config(bts_index, config.ssf_config)

        if config.bandwidth:
            self.set_bandwidth(bts_index, config.bandwidth)

        if config.dl_channel:
            self.set_downlink_channel_number(bts_index, config.dl_channel)

        if config.mimo_mode:
            self.set_mimo_mode(bts_index, config.mimo_mode)

        if config.transmission_mode:
            self.set_transmission_mode(bts_index, config.transmission_mode)

        # Modulation order should be set before set_scheduling_mode being
        # called.
        if config.dl_256_qam_enabled is not None:
            self.set_dl_256_qam_enabled(bts_index, config.dl_256_qam_enabled)

        if config.ul_64_qam_enabled is not None:
            self.set_ul_64_qam_enabled(bts_index, config.ul_64_qam_enabled)

        if config.scheduling_mode:

            if (
                config.scheduling_mode
                == cellular_lib.LteSimulation.SchedulingMode.STATIC
                and not (
                    config.dl_rbs
                    and config.ul_rbs
                    and config.dl_mcs
                    and config.ul_mcs
                )
            ):
                raise ValueError(
                    "When the scheduling mode is set to manual, "
                    "the RB and MCS parameters are required."
                )

            # If scheduling mode is set to Dynamic, the RB and MCS parameters
            # will be ignored by set_scheduling_mode.
            self.set_scheduling_mode(
                bts_index,
                config.scheduling_mode,
                config.dl_mcs,
                config.ul_mcs,
                config.dl_rbs,
                config.ul_rbs,
            )

        # This variable stores a boolean value so the following is needed to
        # differentiate False from None
        if config.mac_padding is not None:
            self.set_mac_padding(bts_index, config.mac_padding)

        if config.cfi:
            self.set_cfi(bts_index, config.cfi)

        if config.paging_cycle:
            self.set_paging_cycle(bts_index, config.paging_cycle)

        if config.phich:
            self.set_phich_resource(bts_index, config.phich)

        if config.drx_connected_mode:
            self.set_drx_connected_mode(bts_index, config.drx_connected_mode)

            if config.drx_on_duration_timer:
                self.set_drx_on_duration_timer(
                    bts_index, config.drx_on_duration_timer
                )

            if config.drx_inactivity_timer:
                self.set_drx_inactivity_timer(
                    bts_index, config.drx_inactivity_timer
                )

            if config.drx_retransmission_timer:
                self.set_drx_retransmission_timer(
                    bts_index, config.drx_retransmission_timer
                )

            if config.drx_long_cycle:
                self.set_drx_long_cycle(bts_index, config.drx_long_cycle)

            if config.drx_long_cycle_offset is not None:
                self.set_drx_long_cycle_offset(
                    bts_index, config.drx_long_cycle_offset
                )

    def configure_nr_bts(self, config, bts_index=1):
        """Commands the equipment to setup an LTE base station with the
        required configuration.

        Args:
            config: an LteSimulation.BtsConfig object.
            bts_index: the base station number.
        """
        if config.band:
            self.set_band(bts_index, config.band)

        if config.nr_arfcn:
            self.set_downlink_channel_number(bts_index, config.nr_arfcn)

        if config.bandwidth:
            self.set_bandwidth(bts_index, config.bandwidth)

        if config.mimo_mode:
            self.set_mimo_mode(bts_index, config.mimo_mode)

        if config.scheduling_mode:

            if (
                config.scheduling_mode
                == cellular_lib.LteSimulation.SchedulingMode.STATIC
                and not (
                    config.dl_rbs
                    and config.ul_rbs
                    and config.dl_mcs
                    and config.ul_mcs
                )
            ):
                raise ValueError(
                    "When the scheduling mode is set to manual, "
                    "the RB and MCS parameters are required."
                )

            # If scheduling mode is set to Dynamic, the RB and MCS parameters
            # will be ignored by set_scheduling_mode.
            self.set_scheduling_mode(
                bts_index,
                config.scheduling_mode,
                config.dl_mcs,
                config.ul_mcs,
                config.dl_rbs,
                config.ul_rbs,
            )
        if config.mac_padding is not None:
            self.set_mac_padding(bts_index, config.mac_padding)

    def set_lte_rrc_state_change_timer(self, enabled, time=10):
        """Configures the LTE RRC state change timer.

        Args:
            enabled: a boolean indicating if the timer should be on or off.
            time: time in seconds for the timer to expire
        """
        raise NotImplementedError()

    def set_band(self, bts_index, band):
        """Sets the band for the indicated base station.

        Args:
            bts_index: the base station number
            band: the new band
        """
        raise NotImplementedError()

    def set_input_power(self, bts_index, input_power):
        """Sets the input power for the indicated base station.

        Args:
            bts_index: the base station number
            input_power: the new input power
        """
        raise NotImplementedError()

    def set_output_power(self, bts_index, output_power):
        """Sets the output power for the indicated base station.

        Args:
            bts_index: the base station number
            output_power: the new output power
        """
        raise NotImplementedError()

    def set_tdd_config(self, bts_index, tdd_config):
        """Sets the tdd configuration number for the indicated base station.

        Args:
            bts_index: the base station number
            tdd_config: the new tdd configuration number
        """
        raise NotImplementedError()

    def set_ssf_config(self, bts_index, ssf_config):
        """Sets the Special Sub-Frame config number for the indicated
        base station.

        Args:
            bts_index: the base station number
            ssf_config: the new ssf config number
        """
        raise NotImplementedError()

    def set_bandwidth(self, bts_index, bandwidth):
        """Sets the bandwidth for the indicated base station.

        Args:
            bts_index: the base station number
            bandwidth: the new bandwidth
        """
        raise NotImplementedError()

    def set_downlink_channel_number(self, bts_index, channel_number):
        """Sets the downlink channel number for the indicated base station.

        Args:
            bts_index: the base station number
            channel_number: the new channel number
        """
        raise NotImplementedError()

    def set_mimo_mode(self, bts_index, mimo_mode):
        """Sets the mimo mode for the indicated base station.

        Args:
            bts_index: the base station number
            mimo_mode: the new mimo mode
        """
        raise NotImplementedError()

    def set_transmission_mode(self, bts_index, transmission_mode):
        """Sets the transmission mode for the indicated base station.

        Args:
            bts_index: the base station number
            transmission_mode: the new transmission mode
        """
        raise NotImplementedError()

    def set_scheduling_mode(
        self, bts_index, scheduling_mode, mcs_dl, mcs_ul, nrb_dl, nrb_ul
    ):
        """Sets the scheduling mode for the indicated base station.

        Args:
            bts_index: the base station number
            scheduling_mode: the new scheduling mode
            mcs_dl: Downlink MCS (only for STATIC scheduling)
            mcs_ul: Uplink MCS (only for STATIC scheduling)
            nrb_dl: Number of RBs for downlink (only for STATIC scheduling)
            nrb_ul: Number of RBs for uplink (only for STATIC scheduling)
        """
        raise NotImplementedError()

    def set_dl_256_qam_enabled(self, bts_index, enabled):
        """Determines what MCS table should be used for the downlink.

        Args:
            bts_index: the base station number
            enabled: whether 256 QAM should be used
        """
        raise NotImplementedError()

    def set_ul_64_qam_enabled(self, bts_index, enabled):
        """Determines what MCS table should be used for the uplink.

        Args:
            bts_index: the base station number
            enabled: whether 64 QAM should be used
        """
        raise NotImplementedError()

    def set_mac_padding(self, bts_index, mac_padding):
        """Enables or disables MAC padding in the indicated base station.

        Args:
            bts_index: the base station number
            mac_padding: the new MAC padding setting
        """
        raise NotImplementedError()

    def set_cfi(self, bts_index, cfi):
        """Sets the Channel Format Indicator for the indicated base station.

        Args:
            bts_index: the base station number
            cfi: the new CFI setting
        """
        raise NotImplementedError()

    def set_paging_cycle(self, bts_index, cycle_duration):
        """Sets the paging cycle duration for the indicated base station.

        Args:
            bts_index: the base station number
            cycle_duration: the new paging cycle duration in milliseconds
        """
        raise NotImplementedError()

    def set_phich_resource(self, bts_index, phich):
        """Sets the PHICH Resource setting for the indicated base station.

        Args:
            bts_index: the base station number
            phich: the new PHICH resource setting
        """
        raise NotImplementedError()

    def set_drx_connected_mode(self, bts_index, active):
        """Sets the time interval to wait before entering DRX mode

        Args:
            bts_index: the base station number
            active: Boolean indicating whether cDRX mode
                is active
        """
        raise NotImplementedError()

    def set_drx_on_duration_timer(self, bts_index, timer):
        """Sets the amount of PDCCH subframes to wait for data after
            waking up from a DRX cycle

        Args:
            bts_index: the base station number
            timer: Number of PDCCH subframes to wait and check for user data
                after waking from the DRX cycle
        """
        raise NotImplementedError()

    def set_drx_inactivity_timer(self, bts_index, timer):
        """Sets the number of PDCCH subframes to wait before entering DRX mode

        Args:
            bts_index: the base station number
            timer: The amount of time to wait before entering DRX mode
        """
        raise NotImplementedError()

    def set_drx_retransmission_timer(self, bts_index, timer):
        """Sets the number of consecutive PDCCH subframes to wait
        for retransmission

        Args:
            bts_index: the base station number
            timer: Number of PDCCH subframes to remain active

        """
        raise NotImplementedError()

    def set_drx_long_cycle(self, bts_index, cycle):
        """Sets the amount of subframes representing a DRX long cycle.

        Args:
            bts_index: the base station number
            cycle: The amount of subframes representing one long DRX cycle.
                One cycle consists of DRX sleep + DRX on duration
        """
        raise NotImplementedError()

    def set_drx_long_cycle_offset(self, bts_index, offset):
        """Sets the offset used to determine the subframe number
        to begin the long drx cycle

        Args:
            bts_index: the base station number
            offset: Number in range 0 to (long cycle - 1)
        """
        raise NotImplementedError()

    def lte_attach_secondary_carriers(self, ue_capability_enquiry):
        """Activates the secondary carriers for CA. Requires the DUT to be
        attached to the primary carrier first.

        Args:
            ue_capability_enquiry: UE capability enquiry message to be sent to
        the UE before starting carrier aggregation.
        """
        raise NotImplementedError()

    def wait_until_attached(self, timeout=120):
        """Waits until the DUT is attached to the primary carrier.

        Args:
            timeout: after this amount of time the method will raise a
                CellularSimulatorError exception. Default is 120 seconds.
        """
        raise NotImplementedError()

    def wait_until_communication_state(self, timeout=120):
        """Waits until the DUT is in Communication state.

        Args:
            timeout: after this amount of time the method will raise a
                CellularSimulatorError exception. Default is 120 seconds.
        """
        raise NotImplementedError()

    def wait_until_idle_state(self, timeout=120):
        """Waits until the DUT is in Idle state.

        Args:
            timeout: after this amount of time the method will raise a
                CellularSimulatorError exception. Default is 120 seconds.
        """
        raise NotImplementedError()

    def wait_until_quiet(self, timeout=120):
        """Waits for all pending operations to finish on the simulator.

        Args:
            timeout: after this amount of time the method will raise a
                CellularSimulatorError exception. Default is 120 seconds.
        """
        raise NotImplementedError()

    def detach(self):
        """Turns off all the base stations so the DUT loose connection."""
        raise NotImplementedError()

    def stop(self):
        """Stops current simulation. After calling this method, the simulator
        will need to be set up again."""
        raise NotImplementedError()

    def start_data_traffic(self):
        """Starts transmitting data from the instrument to the DUT."""
        raise NotImplementedError()

    def stop_data_traffic(self):
        """Stops transmitting data from the instrument to the DUT."""
        raise NotImplementedError()

    def get_measured_pusch_power(self):
        """Queries PUSCH power measured at the callbox.

        Returns:
            The PUSCH power in the primary input port.
        """
        raise NotImplementedError()

    def send_sms(self, message):
        """Sends an SMS message to the DUT.

        Args:
            message: the SMS message to send.
        """
        raise NotImplementedError()


class CellularSimulatorError(Exception):
    """Exceptions thrown when the cellular equipment is unreachable or it"""
