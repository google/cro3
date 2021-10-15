# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import logging
import flask
import traceback

from callbox_utils import CallboxLookup as cbl
from callbox_utils import cmw500_cellular_simulator as cmw
from simulation_utils import ChromebookCellularDut
from simulation_utils import LteSimulation
from flask import request

app = flask.Flask(__name__)
app.config["DEBUG"] = False

class callbox_manager():
    """
    Description goes here
    """

    def configure_callbox(data):
        self.log = logging.getLogger()
        self.host = data['host']
        if data['hardware'] == "CMW":
            self.simulator = cmw.CMW500CellularSimulator(cbl.callboxes[self.host], 22)
        self.dut = ChromebookCellularDut.ChromebookCellularDut(self.host, self.log)
        if data['cellular_type'] == "LTE":
            self.simulation = LteSimulation.LteSimulation(self.simulator,
                                                          self.log,
                                                          self.dut,
                                                          {
                                                              'attach_retries': 1,
                                                              'attach_timeout': 120
                                                          }, None)
        self.parameter_list = data['parameter_list']
        return "OK"

    def begin_simulation(data):
        self.simulation.parse_parameters(self.parameter_list)
        self.simulation.start()
        return "OK"

    def send_sms(data):
        self.simulation.send_sms(data["sms"])
        return "OK"


callbox = callbox_manager()

path_lookup = {
    'config': callbox.configure_callbox,
    'start': callbox.begin_simulation,
    'sms': callbox.send_sms,
}


@app.route('/<path:path>', methods=['GET','POST','PUT','DELETE'])
def entrypoint(path):
    try:
        return path_lookup[path](request.json)
    except Exception as e:
        return "%s:\n%s" % (e, traceback.format_exc()), 500


app.run(host="0.0.0.0", debug=False)

