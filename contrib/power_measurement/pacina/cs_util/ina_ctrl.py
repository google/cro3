# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""INA2xx and IN3221 Driver."""

import logging
import time

from . import _ina2xx
from . import _ina3221


logger = logging.getLogger(__name__)


class InaInst(object):
    """INA Base class."""

    def __init__(self, device, ch_config, reg_info, sample_time=1, **kwargs):

        """INA Base Class Init.

        Measures both shunt and bus during continuous mode.
        Conversion time for Vbus and Vsh are kept same,
        and number of average is statically set to 1024.
        as such:
          minimum sampling time: 2 x 140us x 1 x 1024 x no. of chs
          maximum sampling time: 2x 8.244ms x 1024 x no. of chs,
        resulting in:
          minimum sampling time for 1 ch = 0.287ms
          maximum sampling time for 1 ch = 16.88s
        Based on empirical testing of FTDI I2C access,
        suggested minimum sampling time is 1 s.

        Args:
          device: (object) I2C bus object with pertinent address
          ch_config: (dictionary) containing channel information
          reg_info: (module) containing pertinent register information
          sample_time: (float) interval (seconds) to read from ina device.
        """

        self.device = device
        self.ch_config = ch_config
        self.reg_info = reg_info
        _ = kwargs

        # Only [Shunt and bus, continuous] supported
        self.mode = 7

        # 3 channels in total
        self.channel_count = 0
        self.channel_configuration = 0
        for ch in ch_config:
            self.channel_enable = self.channel_configuration + (1 << (2 - ch))
            self.channel_count = self.channel_count + 1

        self.avg_cnt = 1024

        sampling_times = []
        for conversion_time in self.reg_info.CT:
            sampling_times.append(
                self.avg_cnt
                * conversion_time
                * self.channel_count
                * 2
                / 1000000
            )

        self.sample_time = sample_time
        if self.sample_time < 1:
            logger.warning("Minimum recommended conversion time is 1s.")
            self.sample_time = 1

        self.ct = next(
            x[0] for x in enumerate(sampling_times) if x[1] > self.sample_time
        )

        self.sample_time = sampling_times[self.ct]
        logger.info("Total expected conversion time is %.2f", self.sample_time)
        logger.info("VBUS and VSHUNT CT selected to %d", self.ct)
        logger.info("Average count of %d", self.avg_cnt)

        if self.ct == 7:
            logger.warning(
                "Total conversion time is %.2f. Consider reducing sampling time.",
                self.sample_time,
            )

        self.start_time = None
        self.prev_time = None
        self.data_single = []
        self.acc = {}

        self._reset_acc_data()
        self._reset_device()
        self._update_conf()

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

    def _reset_device(self):
        self.device.write_to(
            self.reg_info.CONF, self.reg_info.RESET.to_bytes(2, byteorder="big")
        )

    def _read_bytes(self, reg, num_bytes):
        val = self.device.read_from(reg, num_bytes)
        return val.hex()

    def _update_conf(self):
        val = (
            (self.channel_enable << self.reg_info.CH_SHIFT)
            + (self.reg_info.AVG[self.avg_cnt] << self.reg_info.AVG_SHIFT)
            + (4 << self.reg_info.VBUS_CT_SHIFT)
            + (4 << self.reg_info.VSHUNT_CT_SHIFT)
            + self.mode
        )
        self.device.write_to(self.reg_info.CONF, val.to_bytes(2, "big"))

    def _read_val(self, reg, num_bytes, signed=False, scale_factor=1):
        val = self.device.read_from(reg, num_bytes)
        return (
            int.from_bytes(val, byteorder="big", signed=signed) * scale_factor
        )

    def _read_vshunt(self, ch=0):
        # VSHUNT register is two's complement number from bit 15 to 3.
        # Divide by 8 to right shift by 3
        return self._read_val(
            self.reg_info.VSHUNT1 + ch * 2,
            2,
            signed=True,
            scale_factor=self.reg_info.VSHUNT_SCALE,
        )

    def _read_vbus(self, ch=0):
        # VSHUNT register is two's complement number from bit 15 to 3.
        # Divide by 8 to right shift by 3
        return self._read_val(
            self.reg_info.VBUS1 + ch * 2,
            2,
            signed=False,
            scale_factor=self.reg_info.VBUS_SCALE,
        )

    def _check_conversion_completed(self):
        """Read converstion ready flag."""
        return self._read_val(self.reg_info.MASK, 2) & self.reg_info.CVRF_MASK

    def log_single(self):
        """Returns vbus, vshunt, power of all chs"""
        self.data_single = []
        for ch in self.ch_config:
            vbus = self._read_vbus(ch)
            cur = self._read_vshunt(ch) / self.ch_config[ch]["rsense"]

            self.data_single.append(
                [self.ch_config[ch]["vname"], vbus, cur, vbus * cur]
            )

    def log_continuous(self, timestamp_global=None):
        _ = timestamp_global

        if self.start_time is None:
            self.start_time = time.time()
            self.prev_time = self.start_time
            self._update_conf()
            return

        time_now = time.time()
        if not self._check_conversion_completed():
            return

        time_delta = time_now - self.prev_time
        self.prev_time = time_now
        if time_delta > 2 * self.sample_time:
            logger.warning("Missed Sample Detected.")

        for ch in self.ch_config:
            vname = self.ch_config[ch]["vname"]
            vbus = self._read_vbus(ch)
            cur = self._read_vshunt(ch) / self.ch_config[ch]["rsense"]
            power = vbus * cur
            self.data.append(
                [time_now, time_now - self.start_time, vname, vbus, cur, power]
            )
            self.acc[vname]["acc_power"] = self.acc[vname]["acc_power"] + power
            self.acc[vname]["count"] = self.acc[vname]["count"] + 1


class Ina3221(InaInst):
    """Ina3221 class."""

    def __init__(self, device, ch_config=None, sample_time=1, **kwargs):
        super().__init__(
            device,
            ch_config,
            _ina3221,
            sample_time,
        )
        logger.info(
            "Initializing INA3221 with address of %d at %fHz",
            device.address,
            device.frequency,
        )


class Ina2xx(InaInst):
    """Ina2xx class."""

    def __init__(self, device, ch_config=None, sample_time=1, **kwargs):
        super().__init__(
            device,
            ch_config,
            _ina2xx,
            sample_time,
        )
        logger.info(
            "Initializing INA3221 with address of %d at %fHz",
            device.address,
            device.frequency,
        )


SUPPORTED_PNS = {
    "ina3221": Ina3221,
    "ina231": Ina2xx,
}
