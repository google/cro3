# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides cmw500 handover functionality."""

# pylint: disable=banned-string-format-function

from enum import Enum

from cellular import handover_simulator as hs
from cellular.callbox_utils import cmw500


class HandoverMode(Enum):
    """Supported handover modes."""

    Redirection = "RED"
    MTCSFallback = "MTCS"
    Handover = "HAND"


class Cmw500HandoverSimulator(hs.AbstractHandoverSimulator):
    """Provides methods for performing inter/intra-RAT handovers."""

    def __init__(self, cmw):
        """Init method to setup handover controller.

        Args:
            cmw: the CMW500 instrument.
        """
        self.cmw = cmw
        self._lte = Cmw500LteHandoverManager(self.cmw)
        self._wcdma = Cmw500WcdmaHandoverManager(self.cmw)

    def lte_handover(self, band, channel, bandwidth, source_technology):
        """Performs a handover to LTE.

        Args:
            band: the band of the handover destination.
            channel: the downlink channel of the handover destination.
            bandwidth: the downlink bandwidth of the handover destination.
            source_technology: the source handover technology.
        """
        mode = (
            cmw500.DuplexMode.TDD
            if 33 <= int(band) <= 46
            else cmw500.DuplexMode.FDD
        )
        band = "OB{}".format(band)
        bandwidth = cmw500.BandwidthFromFloat(bandwidth)

        source = self._get_handover_manager(source_technology)
        self._prepare_handover(source, self._lte)
        self._lte.configure_incoming_handover_lte(
            mode, band, channel, bandwidth
        )
        self._perform_handover(source, self._lte)

    def wcdma_handover(self, band, channel, source_technology):
        """Performs a handover to WCDMA.

        Args:
            band: the band of the handover destination.
            channel: the downlink channel of the handover destination.
            source_technology: the source handover technology.
        """
        band = "OB{}".format(band)

        source = self._get_handover_manager(source_technology)
        self._prepare_handover(source, self._wcdma)
        self._wcdma.configure_incoming_handover_wcdma(band, channel)
        self._perform_handover(source, self._wcdma)

    def _prepare_handover(self, source, destination):
        """Initializes the source and destination signalling applications for a handover.

        Args:
            source: the source handover manager.
            destination: the destination handover manager.
        """
        if not source.is_attached:
            raise hs.HandoverSimulatorError(
                "Unable to perform handover, source signalling application is not attached."
            )

        source.handover_destination = destination.application_name
        if source.is_internal_handover:
            destination.wait_for_signalling_state(
                [
                    cmw500.SignallingState.ReadyForHandover.value,
                    cmw500.SignallingState.ON.value,
                ]
            )
            source.handover_mode = HandoverMode.Redirection
        else:
            destination.wait_for_signalling_state(
                [cmw500.SignallingState.ReadyForHandover.value]
            )
            source.handover_mode = HandoverMode.Handover

    def _perform_handover(self, source, destination):
        """Performs the handover and wait for completion.

        Args:
            source: the source handover manager.
            destination: the destination handover manager.
        """
        source.initiate_handover()
        destination.wait_for_handover()
        if not source.is_attached:
            source.stop_signalling()

        self.cmw.wait_until_quiet()

    def _get_handover_manager(self, technology):
        """Gets the handover manager for the specified technology.

        Args:
            technology: the handover source/destination technology.

        Returns:
            the manager for the specified technology.
        """
        if technology == hs.CellularTechnology.LTE:
            return self._lte
        if technology == hs.CellularTechnology.WCDMA:
            return self._wcdma
        raise hs.HandoverSimulatorError(
            "Unsupported handover destination type {}.".format(technology)
        )


class Cmw500HandoverManagerBase:
    """Provides common CMW500 functionality for conducting handovers."""

    def __init__(self, cmw, technology):
        """Initializes handover controller.

        Args:
            cmw: the CMW500 instrument.
            technology: the cellular technology to use.
        """
        self.cmw = cmw
        self.tech = technology.value

    @property
    def application_name(self):
        """Gets the name of the signalling application to be used in handovers."""
        return "{} Sig1".format(self.tech)

    @property
    def handover_destination(self):
        """Gets the handover destination application."""
        cmd = "PREPare:{}:SIGN:HANDover:DESTination?".format(self.tech)
        return self.cmw.send_and_recv(cmd).strip("\"'")

    @property
    def is_internal_handover(self):
        """Returns true if the handover is within the same signalling application."""
        return self.handover_destination == self.application_name

    @handover_destination.setter
    def handover_destination(self, destination):
        """Sets the handover destination application."""
        cmd = 'PREPare:{}:SIGN:HANDover:DESTination "{}"'.format(
            self.tech, destination
        )
        self.cmw.send_and_recv(cmd)

    @property
    def handover_mode(self):
        """Gets the handover mechanism to use."""
        cmd = "PREPare:{}:SIGN:HANDover:MMODe?".format(self.tech)
        return self.cmw.send_and_recv(cmd)

    @handover_mode.setter
    def handover_mode(self, mode):
        """Sets the handover mechanism to use."""
        if not isinstance(mode, HandoverMode):
            raise ValueError("mode should be the instance of HandoverMode.")
        self.cmw.send_and_recv(
            "PREPare:{}:SIGN:HANDover:MMODe {}".format(self.tech, mode.value)
        )

    @property
    def is_attached(self):
        """Returns True if the current technology pswitched state is attached."""
        cmd = "FETCh:{}:SIGN:PSWitched:STATe?".format(self.tech)
        return self.cmw.send_and_recv(cmd) in self.get_attached_states()

    def stop_signalling(self):
        """Stops the current signalling application."""
        cmd = "SOURce:{}:SIGN:CELL:STATe {}".format(
            self.tech, cmw500.SignallingState.OFF.value
        )
        self.cmw.send_and_recv(cmd)
        self.wait_for_signalling_state([cmw500.SignallingState.OFF.value])

    def wait_for_signalling_state(self, allowed, timeout=30):
        """Polls the signalling state until it reaches an allowable state.

        Args:
            allowed: a list of strings defining allowed signalling state responses.
            timeout: timeout for valid state to be reached.

        Raises:
            CmwError on time out.
        """
        allowed = set(["{},ADJ".format(state) for state in allowed])
        cmd = "SOURce:{}:SIGN:CELL:STATe:ALL?".format(self.tech)
        self.cmw.wait_for_response(cmd, allowed, timeout=timeout)

    def wait_for_pswitched_state(self, allowed, timeout=120):
        """Polls the pswitched state until it reaches an allowable state.

        Args:
            allowed: a list of strings defining valid pswitched state responses.
            timeout: timeout for valid state to be reached.

        Raises:
            CmwError on time out.
        """
        cmd = "FETCh:{}:SIGN:PSWitched:STATe?".format(self.tech)
        self.cmw.wait_for_response(cmd, allowed, timeout=timeout)

    def get_attached_states(self):
        """Gets a collection of valid responses when the application is attached.

        Returns:
            states: the list of valid attached states.
        """
        raise NotImplementedError()

    def initiate_handover(self):
        """Initiates an outgoing handover."""
        raise NotImplementedError()

    def wait_for_handover(self):
        """Waits for an incoming handover to be completed."""
        raise NotImplementedError()


class Cmw500LteHandoverManager(Cmw500HandoverManagerBase):
    """Provides LTE-specific handover methods."""

    ATTACHED_STATES = [cmw500.LTE_ATTACH_RESP]

    def __init__(self, cmw):
        """Init method to setup handover controller.

        Args:
            cmw: the CMW500 instrument.
        """
        super().__init__(cmw, hs.CellularTechnology.LTE)

    def configure_incoming_handover_lte(self, mode, band, channel, bandwidth):
        """Prepares the LTE simulator for an incoming handover.

        Args:
            mode: the duplexing mode of the handover destination.
            band: the band of the handover destination.
            channel: the downlink channel of the handover destination.
            bandwidth: the duplexing mode of the handover destination.
        """
        if self.is_attached:
            self.configure_handover(mode, band, channel, bandwidth)
        else:
            bts = self.cmw.get_base_station()
            bts.duplex_mode = mode
            bts.band = band
            bts.dl_channel = channel
            bts.bandwidth = bandwidth

    def initiate_handover(self):
        """Initiates an outgoing handover."""
        self.cmw.send_and_recv("CALL:LTE:SIGN:PSWitched:ACTion HANDover")

    def wait_for_handover(self):
        """Waits for an incoming handover to be completed."""
        self.cmw.wait_for_attached_state()

    def configure_handover(self, mode, band, channel, bandwidth, emit="NS01"):
        """Configures the handover destination.

        Args:
            mode: the duplexing mode of the handover destination.
            band: the band of the handover destination.
            channel: the downlink channel of the handover destination.
            bandwidth: the downlink bandwidth of the handover destination.
            emit: an additional optional spectrum emissions requirement.
        """
        if not isinstance(bandwidth, cmw500.LteBandwidth):
            raise ValueError(
                "bandwidth should be an instance of " "LteBandwidth."
            )
        if not isinstance(mode, cmw500.DuplexMode):
            raise ValueError("mode should be an instance of " "DuplexMode.")
        self.cmw.send_and_recv(
            "PREPare:LTE:SIGN:HANDover:ENHanced {}, {}, {}, {}, {}".format(
                mode.value, band, channel, bandwidth.value, emit
            )
        )

    def get_attached_states(self):
        """Gets a collection of valid attached states.

        Returns:
            states: the list of valid attached states.
        """
        return self.ATTACHED_STATES


class Cmw500WcdmaHandoverManager(Cmw500HandoverManagerBase):
    """Provides WCDMA-specific handover methods."""

    ATTACHED_STATES = set(
        [cmw500.WCDMA_ATTACH_RESP, cmw500.WCDMA_CESTABLISHED_RESP]
    )

    def __init__(self, cmw):
        """Init method to setup handover controller.

        Args:
            cmw: the CMW500 instrument.
        """
        super().__init__(cmw, hs.CellularTechnology.WCDMA)
        self._stored_band = self._band
        self._stored_channel = self._dl_channel

    @property
    def _band(self):
        """Sets the signalling application band."""
        self.cmw.send_and_recv("CONFigure:WCDMa:SIGN:CARRier:BAND?")

    @_band.setter
    def _band(self, band):
        """Sets the signalling application band.

        Args:
            band: the band of the signalling application.
        """
        cmd = "CONFigure:WCDMa:SIGN:CARRier:BAND {}".format(band)
        self.cmw.send_and_recv(cmd)

    @property
    def _dl_channel(self):
        """Gets the signalling application dl channel."""
        cmd = "CONFigure:WCDMa:SIGN:RFSettings:CARRier:CHANnel:DL?"
        self.cmw.send_and_recv(cmd)

    @_dl_channel.setter
    def _dl_channel(self, channel):
        """Sets the signalling application dl channel.

        Args:
            channel: the channel of the signalling application.
        """
        cmd = "CONFigure:WCDMa:SIGN:RFSettings:CARRier:CHANnel:DL {}".format(
            channel
        )
        self.cmw.send_and_recv(cmd)

    def configure_incoming_handover_wcdma(self, band, channel):
        """Prepares the WCDMA simulator for an incoming handover.

        Args:
            band: the band of the handover destination.
            channel: the downlink channel of the handover destination.
        """
        # WCDMA has no dedicated configuration for handovers within the same
        # signalling application instead, store the values for later and
        # apply them when initiate_handover is called.
        if not self.is_attached:
            self._band = band
            self._dl_channel = channel

        self._stored_band = band
        self._stored_channel = channel

    def initiate_handover(self):
        """Initiates an outgoing handover."""
        if self.is_internal_handover:
            self._dl_channel = self._stored_channel
            self._band = self._stored_band
        else:
            self.cmw.send_and_recv("CALL:WCDMA:SIGN:PSWitched:ACTion HANDover")

    def wait_for_handover(self):
        """Waits for an incoming handover to be completed."""
        self.wait_for_pswitched_state(
            [cmw500.WCDMA_ATTACH_RESP, cmw500.WCDMA_CESTABLISHED_RESP]
        )

    def get_attached_states(self):
        """Gets a collection of valid attached states.

        Returns:
            states: the list of valid attached states.
        """
        return self.ATTACHED_STATES
