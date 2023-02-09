# -*- coding: utf-8 -*-

# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Classes related to loading config data"""

import importlib.util


class PacSensor:
    """Data for a measurement point"""

    def __init__(self, addr, channel, name, nom, rsense):
        """Data constructor"""
        self.addr = addr
        self.channel = channel
        self.name = name
        self.nom = nom
        self.rsense = rsense


class PacGpio:
    """Data for a GPIO"""

    def __init__(self, addr, rail):
        """Data constructor"""
        self.addr = addr
        self.rail = rail


class PacRail:
    """Data for a rail"""

    def __init__(self, rail, parent):
        """Data constructor"""
        self.rail = rail
        self.parent = parent


class PacConfig:
    """Contains measurement point, gpio and rail data"""

    def __init__(self, config_path):
        """Loads config from the given path"""
        spec = importlib.util.spec_from_file_location("config", config_path)
        config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(config)

        self.pacs = []
        self.rails = []
        self.gpios = []
        self.pacs_by_addr = {}

        # Create our sensors, also group them by i2c address
        for (addr, name, nom, rsense) in config.PACS:
            addr_parts = addr.split(":")
            addr = int(addr_parts[0], 16)
            channel = addr_parts[1]

            if addr not in self.pacs_by_addr:
                self.pacs_by_addr[addr] = []

            sensor = PacSensor(addr, channel, name, nom, rsense)
            self.pacs_by_addr[addr].append(sensor)
            self.pacs.append(sensor)

        for (rail, parent) in config.RAILS:
            self.rails.append(PacRail(rail, parent))

        for (addr, rail) in config.GPIOS:
            self.gpios.append(PacGpio(addr, rail))
