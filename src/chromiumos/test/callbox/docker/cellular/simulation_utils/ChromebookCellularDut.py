# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Provides cellular DUT implementation for CrOS devices."""

from acts.controllers.cellular_lib import BaseCellularDut


class ChromebookCellularDut(BaseCellularDut.BaseCellularDut):
    """Chromebook implementation of the cellular DUT class."""

    def __init__(self, ad, logger):
        """Keeps a handler to the chromebook device.

        Args:
           ad: a handle to the chromebook device
           logger: a handler to the logger object
        """
        self.ad = ad
        self.log = logger

    def toggle_airplane_mode(self, new_state=True):
        """Turns on and off mobile data."""

    def toggle_data_roaming(self, new_state=True):
        """Enables or disables cellular data roaming.

        Args:
          new_state: True if data roaming needs to be enabled.
        """

    def get_rx_tx_power_levels(self):
        """Not relevant to Chromebooks, but required interface for compatibility."""
        return (None, None)

    def set_apn(self, name, apn, type="default"):  # pylint: disable=W0622
        """Not currently supported by Chromebooks yet."""

    def set_preferred_network_type(self, type):  # pylint: disable=W0622
        """Sets the preferred RAT.

        Args:
          type: an instance of class PreferredNetworkType
        """

    def get_telephony_signal_strength(self):
        """Not relevant to Chromebooks, but required interface for compatibility."""

    def start_modem_logging(self):
        """Starts on-device log collection."""

    def stop_modem_logging(self):
        """Stops log collection and pulls logs."""
