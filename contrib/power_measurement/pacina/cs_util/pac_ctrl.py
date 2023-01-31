# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Utilities for reading from PAC19xx sensors."""

import logging
import time

from . import _pac19xx
import cs_types

logger = logging.getLogger(__name__)


class Pac19xxInst:
    """Base PAC19xx Class."""

    _REFRESH_WAIT_TIME = 0.001

    def __init__(
        self,
        device,
        ch_config=None,
        polarity=cs_types.Polarity.UNIPOLAR,
        refresh_global=False,
        p_polar=None,
        p_bit_shift=None,
        v_polar=None,
        **kwargs
    ):

        """Base PAC19XX class init.

        Args:
          device: (object) I2C bus object with pertinent address
          ch_config: (dictionary) containing channel information
          polarity: (string) PAC19XX polarity to use
          refresh_global: (boolean) Enable global refresh
          p_polar: Coefficient for power calculations
          p_bit_shift: bit shifting during power read
          v_polar: Coefficient for voltage calculations
        """

        self.device = device
        self.polarity = polarity
        self.ch_config = ch_config

        self.data = []
        self.data_single = []
        self.acc = {}
        self.start_time = None
        self._p_polar = p_polar
        self._v_polar = v_polar
        self._p_bit_shift = p_bit_shift
        _ = kwargs

        """ REFRESH_G is called during the data read.
        All Pac19xxInst with ch_config should not send REFRESH_G
        if refresh_global is True. Pac19xxInst with addr of 0,
        should issue REFRESH_G when refresh_global is True.
        The following inversion of refresh_global enables the
        above logic for Pac19xxInst with addr of 0, where it will
        not have a valid ch_config.
        """

        if ch_config:
            self.refresh_global = refresh_global
            self._set_polarity()
            self._disable_slow()
            self._reset_acc_data()
        else:
            self.refresh_global = False

    def _reset_acc_data(self):
        self.start_time = None
        self.data = []
        for ch in self.ch_config.keys():
            vname = self.ch_config[ch]["vname"]
            self.acc[vname] = {}
            self.acc[vname]["acc_raw"] = 0
            self.acc[vname]["count"] = 0
            self.acc[vname]["acc_power"] = 0
            self.acc[vname]["rsense"] = self.ch_config[ch]["rsense"]

    def _reset_accumulator(self):
        """Sends REFRESH command to the target PAC19xx.

        Actual command used is REFRESH_G command, which
        has same properties as the REFRESH command with
        the possibility of being compatible with the I2C
        general call address.
        """
        logger.debug("Resetting Accumulator")
        self.device.write_to(_pac19xx.REFRESH_G, 0)
        time.sleep(self._REFRESH_WAIT_TIME)

    def _read_bytes(self, reg, num_bytes):
        val = self.device.read_from(reg, num_bytes)
        return val.hex()

    def _read_val(self, reg, num_bytes, signed=False, scale_factor=1):
        val = self.device.read_from(reg, num_bytes)
        return (
            int.from_bytes(val, byteorder="big", signed=signed) * scale_factor
        )

    def _read_voltage(self, ch=0):
        val = self._read_val(_pac19xx.VBUS1_AVG + int(ch), 2)
        return float(val * (_pac19xx.FSV / self._v_polar[self.polarity]))

    def _read_current(self, ch=0):
        val = self._read_val(_pac19xx.VSENSE1_AVG + int(ch), 2)
        fsc = _pac19xx.FSR / float(self.ch_config[ch]["rsense"])
        return float(fsc / _pac19xx.V_POLAR[self.polarity]) * val

    def _read_power(self, ch=0):
        val = self._read_val(
            _pac19xx.VPOWER1 + int(ch),
            4,
            signed=(self.polarity == cs_types.Polarity.BIPOLAR),
        )
        fs = _pac19xx.FSR / float(self.ch_config[ch]["rsense"]) * _pac19xx.FSV
        return (
            fs * val / self._p_polar[self.polarity] / (2**self._p_bit_shift)
        )

    def log_single(self):
        """Returns vbus, vsense and power readings of all chs."""
        if not self.refresh_global:
            self._reset_accumulator()

        if self.ch_config is None:
            return

        self.data_single = []

        for ch in self.ch_config:
            vbus = self._read_voltage(ch)
            ishunt = self._read_current(ch)
            self.data_single.append(
                [
                    self.ch_config[ch]["vname"],
                    self._read_voltage(ch),
                    self._read_current(ch),
                    vbus * ishunt,
                ]
            )

    def log_continuous(self, timestamp_global=None):
        """Returns acc reading of all chs."""

        # Discarding first sample to ensure similar sample count for
        # current sensors on different FTDI buses
        discard_sample = False

        if not self.refresh_global:
            self._reset_accumulator()

        if self.start_time is None:
            if self.refresh_global:
                self.start_time = timestamp_global
            else:
                self.start_time = time.time()
            discard_sample = True

        if self.ch_config is None:
            return

        for ch in self.ch_config:
            (accum, count) = self._dump_accumulator(ch)
            if (
                count == 0
                or discard_sample
                or self.ch_config[ch]["rsense"] == 0
            ):
                continue
            if self.refresh_global:
                time_now = timestamp_global
            else:
                time_now = time.time()

            power = (
                accum
                / (self._p_polar[self.polarity] * count)
                * 3.2
                / self.ch_config[ch]["rsense"]
            )
            vname = self.ch_config[ch]["vname"]

            self.data.append(
                [
                    time_now,
                    time_now - self.start_time,
                    vname,
                    accum,
                    count,
                    power,
                ]
            )
            self.acc[vname]["acc_raw"] += accum
            self.acc[vname]["count"] += count
            self.acc[vname]["acc_power"] += power * count


class Pac193xInst(Pac19xxInst):
    """PAC193X Class.

    Support PAC1932,1933,1934
    """

    def __init__(
        self,
        device,
        ch_config=None,
        polarity=cs_types.Polarity.UNIPOLAR,
        refresh_global=False,
        **kwargs
    ):
        super().__init__(
            device,
            ch_config,
            polarity,
            refresh_global,
            p_polar=_pac19xx.P_POLAR_193x,
            v_polar=_pac19xx.V_POLAR,
            p_bit_shift=4,
        )
        logger.info(
            "Initializing PAC193x with address of %d at %fHz",
            device.address,
            device.frequency,
        )

    def _disable_slow(self):
        logger.info("Disabling SLOW for PAC193X")
        self.device.write_to(_pac19xx.CTRL, b"\x08")
        self.device.write_to(_pac19xx.REFRESH, 0)
        time.sleep(self._REFRESH_WAIT_TIME)

    def _enable_slow(self):
        self.device.write_to(_pac19xx.CTRL, b"\x00")
        self.device.write_to(_pac19xx.REFRESH, 0)
        time.sleep(self._REFRESH_WAIT_TIME)

    def _dump_accumulator(self, ch=0):
        signed = False
        if self.polarity == cs_types.Polarity.BIPOLAR:
            signed = True

        # PAC193x VACCn (6 bytes)
        reg = self._read_val(_pac19xx.VACC1 + ch, 6, signed=signed)
        # PAC193x ACC_COUNTER (3 bytes)
        count = self._read_val(_pac19xx.ACC_COUNT, 3)
        return (reg, count)

    def _set_polarity(self):
        reg = b"\x00"
        if self.polarity == cs_types.Polarity.UNIPOLAR:
            reg = b"\x00"
        elif self.polarity == cs_types.Polarity.BIPOLAR:
            reg = b"\xFF"
        else:
            raise ValueError("Unsupported polarity type " + self.polarity)
        self.device.write_to(_pac19xx.NEG_PWR_FSR, reg)


class Pac195xInst(Pac19xxInst):
    """PAC195X Class.

    Support PAC1952,1953,1954
    """

    def __init__(
        self,
        device,
        ch_config=None,
        polarity=cs_types.Polarity.UNIPOLAR,
        refresh_global=False,
        **kwargs
    ):

        super().__init__(
            device,
            ch_config,
            polarity,
            refresh_global,
            p_polar=_pac19xx.P_POLAR_195x,
            v_polar=_pac19xx.V_POLAR,
            p_bit_shift=2,
        )
        self.gpio = None
        logger.info(
            "Initializing PAC195x with address of " "%d at %fHz",
            device.address,
            device.frequency,
        )

    def set_gpio_name(self, rail):
        self.gpio = rail

    def _disable_slow(self):
        logger.info("Disabling SLOW for PAC195X")
        self.device.write_to(_pac19xx.CTRL, b"\x05\x00")
        self.device.write_to(_pac19xx.REFRESH, 0)
        time.sleep(self._REFRESH_WAIT_TIME)

    def _enable_slow(self):
        self.device.write_to(_pac19xx.CTRL, b"\x07\x00")
        self.device.write_to(_pac19xx.REFRESH, 0)
        time.sleep(self._REFRESH_WAIT_TIME)

    def _dump_accumulator(self, ch=0):

        reg = self._read_val(
            _pac19xx.VACC1 + ch,
            7,
            signed=(self.polarity == cs_types.Polarity.BIPOLAR),
        )
        count = self._read_val(_pac19xx.ACC_COUNT, 4)
        return (reg, count)

    def read_gpio(self):
        return bool(self._read_val(_pac19xx.SMBUS_SET, 1) & (1 << 7))

    def _set_polarity(self):
        if self.polarity == cs_types.Polarity.UNIPOLAR:
            reg = b"\x00\x00"
        elif self.polarity == cs_types.Polarity.BIPOLAR:
            reg = b"\x55\x55"
        else:
            raise ValueError("Unsupported polarity type " + self.polarity)
        self.device.write_to(_pac19xx.NEG_PWR_FSR, reg)


SUPPORTED_PNS = {
    "pac195x": Pac195xInst,
    "pac1954": Pac195xInst,
    "pac1931": Pac193xInst,
    "pac1932": Pac193xInst,
    "pac1933": Pac193xInst,
    "pac1934": Pac193xInst,
}
