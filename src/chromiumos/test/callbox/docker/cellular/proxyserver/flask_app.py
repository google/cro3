# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import flask
import traceback

from ..callbox_utils import cmw500_cellular_simulator as cmw
from ..simulation_utils import ChromebookCellularDut
from ..simulation_utils import LteSimulation
from flask import request

app = flask.Flask(__name__)
app.config["DEBUG"] = False

available_callboxes = [
    'chromeos1-donutlab-callbox1.cros',
    'chromeos1-donutlab-callbox2.cros',
    'chromeos1-donutlab-callbox3.cros',
    'chromeos1-donutlab-callbox4.cros'
]


class CallboxConfiguration:
    def __init__(self):
        self.host = None
        self.dut = None
        self.simulator = None
        self.simulation = None
        self.parameter_list = None

class CallboxManager:
    """
    Description goes here
    """

    def __init__(self):
        self.configs_by_host = dict()

    def configure_callbox(self, data):
        self._require_dict_keys(data, "callbox", "hardware", "cellular_type", "parameter_list")
        config = self._get_callbox_config(data['callbox'], True)
        if data['hardware'] == "CMW":
            config.simulator = cmw.CMW500CellularSimulator(config.host, 5025, app.logger)
        config.dut = ChromebookCellularDut.ChromebookCellularDut("no_dut_connection", app.logger)
        if data['cellular_type'] == "LTE":
            config.simulation = LteSimulation.LteSimulation(config.simulator,
                                                          app.logger,
                                                          config.dut,
                                                          {
                                                              'attach_retries': 1,
                                                              'attach_timeout': 120
                                                          }, None)
        config.parameter_list = data['parameter_list']
        return "OK"

    def begin_simulation(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data['callbox'])
        config.simulation.parse_parameters(config.parameter_list)
        config.simulation.start()
        return "OK"

    def send_sms(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data['callbox'])
        config.simulation.send_sms(data["sms"])
        return "OK"

    def _get_callbox_config(self, callbox, create_if_dne=False):
        if callbox not in available_callboxes:
            raise ValueError("Callbox '{}' is not one of the available callboxes: {}".format(callbox, available_callboxes))
        if callbox not in self.configs_by_host:
            if create_if_dne:
                config = CallboxConfiguration()
                config.host = callbox
                self.configs_by_host[callbox] = config
            else:
                raise ValueError("Callbox '{}' not configured".format(callbox))
        return self.configs_by_host[callbox]

    @staticmethod
    def _require_dict_keys(d, *keys):
        for key in keys:
            if key not in d:
                raise Exception("Missing required data key '{}'".format(key))

callbox_manager = CallboxManager()

path_lookup = {
    'config': callbox_manager.configure_callbox,
    'start': callbox_manager.begin_simulation,
    'sms': callbox_manager.send_sms,
}


@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def entrypoint(path):
    try:
        return path_lookup[path](request.json)
    except Exception as e:
        return "%s:\n%s" % (e, traceback.format_exc()), 500


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
