# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# TODO(b/254347891): unify formatting and ignore specific lints in callbox libraries
# pylint: skip-file

from . import simulation_utils as sims


class AbstractCellularSimulator:
    """A generic cellular simulator controller class that can be derived to
    implement equipment specific classes and allows the tests to be implemented
    without depending on a singular instrument model.

    This class defines the interface that every cellular simulator controller
    needs to implement and shouldn't be instantiated by itself."""

    # Indicates if it is able to use 256 QAM as the downlink modulation for LTE
    LTE_SUPPORTS_DL_256QAM = None

    # Indicates if it is able to use 64 QAM as the uplink modulation for LTE
    LTE_SUPPORTS_UL_64QAM = None

    # Indicates if 4x4 MIMO is supported for LTE
    LTE_SUPPORTS_4X4_MIMO = None

    # The maximum number of carriers that this simulator can support for LTE
    LTE_MAX_CARRIERS = None

    # The maximum power that the equipment is able to transmit
    MAX_DL_POWER = None

    def __init__(self):
        """Initializes the cellular simulator.  Logger init goes here."""

    def destroy(self):
        """Sends finalization commands to the cellular equipment and closes
        the connection."""
        raise NotImplementedError()

    def setup_lte_scenario(self):
        """Configures the equipment for an LTE simulation."""
        raise NotImplementedError()

    def setup_lte_ca_scenario(self):
        """Configures the equipment for an LTE with CA simulation."""
        raise NotImplementedError()

    def set_ca_combination(self, combination):
        """Prepares the test equipment for the indicated CA combination.

        The reason why this is implemented in a separate method and not calling
        LteSimulation.BtsConfig for each separate band is that configuring each
        ssc cannot be done separately, as it is necessary to know which
        carriers are on the same band in order to decide which RF outputs can
        be shared in the test equipment.

        Args:
            combination: carrier aggregation configurations are indicated
                with a list of strings consisting of the band number followed
                by the CA class. For example, for 5 CA using 3C 7C and 28A
                the parameter value should be [3c, 7c, 28a].
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

        if config.output_power is not None:
            self.set_output_power(bts_index, config.output_power)

        if config.input_power is not None:
            self.set_input_power(bts_index, config.input_power)

        if isinstance(config, sims.LteSimulation.LteSimulation.BtsConfig):
            self.configure_lte_bts(config, bts_index)

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
        if config.dl_modulation_order:
            self.set_dl_modulation(bts_index, config.dl_modulation_order)

        if config.ul_modulation_order:
            self.set_ul_modulation(bts_index, config.ul_modulation_order)

        if config.scheduling_mode:

            if (
                config.scheduling_mode
                == sims.LteSimulation.SchedulingMode.STATIC
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
        if config.tbs_pattern_on is not None:
            self.set_tbs_pattern_on(bts_index, config.tbs_pattern_on)

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

    def set_dl_modulation(self, bts_index, modulation):
        """Sets the DL modulation for the indicated base station.

        Args:
            bts_index: the base station number
            modulation: the new DL modulation
        """
        raise NotImplementedError()

    def set_ul_modulation(self, bts_index, modulation):
        """Sets the UL modulation for the indicated base station.

        Args:
            bts_index: the base station number
            modulation: the new UL modulation
        """
        raise NotImplementedError()

    def set_tbs_pattern_on(self, bts_index, tbs_pattern_on):
        """Enables or disables TBS pattern in the indicated base station.

        Args:
            bts_index: the base station number
            tbs_pattern_on: the new TBS pattern setting
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

    def send_sms(self, sms_message):
        """Sends SMS message from the instrument to the DUT."""
        raise NotImplementedError()


class CellularSimulatorError(Exception):
    """Exceptions thrown when the cellular equipment is unreachable or it
    returns an error after receiving a command."""

    pass
