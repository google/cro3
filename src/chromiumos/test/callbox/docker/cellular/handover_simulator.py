# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Provides handover functionality."""

from enum import Enum


class CellularTechnology(Enum):
    """A supported cellular technology to handover to/from."""
    LTE = 'LTE'
    WCDMA = 'WCDMA'


class AbstractHandoverSimulator:
    """Simulator for facilitating inter/intra-RAT handovers."""

    def lte_handover(self, band, channel, bandwidth, source_technology):
        """Performs a handover to LTE.

        Args:
            band: the band of the handover destination
            channel: the downlink channel of the handover destination
            bandwidth: the downlink bandwidth of the handover destination
            source_technology: the source handover technology.
        """
        raise NotImplementedError()

    def wcdma_handover(self, band, channel, source_technology):
        """Performs a handover to WCDMA.

        Args:
            band: the band of the handover destination
            channel: the downlink channel of the handover destination
            source_technology: the source handover technology.
        """
        raise NotImplementedError()


class HandoverSimulatorError(Exception):
    """Exceptions thrown when the cellular equipment is unable to successfully perform a handover operation."""
