# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from enum import Enum


class PreferredNetworkType(Enum):
    """ Available preferred network types that can be passed to
  set_preferred_network_type"""
    LTE_ONLY = 'lte-only'
    GSM_ONLY = 'gsm-only'
    WCDMA_ONLY = 'wcdma-only'


class BaseCellularDut():
    """ Base class for DUTs used with cellular simulators. """

    def toggle_airplane_mode(self, new_state=True):
        """ Turns airplane mode on / off.

        Args:
          new_state: True if airplane mode needs to be enabled.
        """
        raise NotImplementedError()

    def toggle_data_roaming(self, new_state=True):
        """ Enables or disables cellular data roaming.

        Args:
          new_state: True if data roaming needs to be enabled.
        """
        raise NotImplementedError()

    def get_rx_tx_power_levels(self):
        """ Obtains Rx and Tx power levels measured from the DUT.

        Returns:
          A tuple where the first element is an array with the RSRP value
          in each Rx chain, and the second element is the Tx power in dBm.
          Values for invalid or disabled Rx / Tx chains are set to None.
        """
        raise NotImplementedError()

    def set_apn(self, name, apn, type='default'):
        """ Sets the Access Point Name.

        Args:
          name: the APN name
          apn: the APN
          type: the APN type
        """
        raise NotImplementedError()

    def set_preferred_network_type(self, type):
        """ Sets the preferred RAT.

        Args:
          type: an instance of class PreferredNetworkType
        """
        raise NotImplementedError()

    def get_telephony_signal_strength(self):
        """ Wrapper for the method with the same name in tel_utils.

        Will be deprecated and replaced by get_rx_tx_power_levels. """
        raise NotImplementedError()
