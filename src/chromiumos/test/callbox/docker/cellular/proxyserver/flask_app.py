# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Proxy server for configuring callboxes."""

# disable some lints to stay consistent with ACTS formatting
# pylint: disable=bad-indentation, banned-string-format-function
# pylint: disable=docstring-trailing-quotes, docstring-section-indent

import traceback
import urllib

import flask  # pylint: disable=E0401
from flask import request  # pylint: disable=E0401

from ..callbox_utils import cmw500_cellular_simulator as cmw
from ..simulation_utils import ChromebookCellularDut
from ..simulation_utils import LteSimulation


app = flask.Flask(__name__)
app.config['DEBUG'] = False

class CallboxConfiguration:
    """Callbox access configuration."""
    def __init__(self):
        self.host = None
        self.port = None
        self.dut = None
        self.simulator = None
        self.simulation = None
        self.parameter_list = None
        self.iperf = None

class CallboxManager:
    """Manager object that holds configurations to known callboxes."""

    def __init__(self):
        self.configs_by_host = dict()

    def configure_callbox(self, data):
        self._require_dict_keys(
                data, 'callbox', 'hardware',
                'cellular_type', 'parameter_list')
        config = self._get_callbox_config(data['callbox'], True)
        if data['hardware'] == 'CMW':
            config.simulator = cmw.CMW500CellularSimulator(
                    config.host, config.port, app.logger)
            config.iperf = config.simulator.cmw.init_perf_measurement()

        config.dut = ChromebookCellularDut.ChromebookCellularDut(
                'no_dut_connection', app.logger)
        if data['cellular_type'] == 'LTE':
            config.simulation = LteSimulation.LteSimulation(
                    config.simulator, app.logger, config.dut,
                    {
                            'attach_retries': 1,
                            'attach_timeout': 120
                    }, None)

        config.parameter_list = data['parameter_list']
        config.simulation.parse_parameters(config.parameter_list)
        return 'OK'

    def begin_simulation(self, data):
        self._require_dict_keys(data, 'callbox')
        config = self._get_callbox_config(data['callbox'])
        config.simulation.start()
        return 'OK'

    def set_uplink_tx_power(self, data):
        self._require_dict_keys(data, 'callbox', LteSimulation.LteSimulation.PARAM_UL_PW)
        config = self._get_callbox_config(data['callbox'])
        parameters = [LteSimulation.LteSimulation.PARAM_UL_PW, data[LteSimulation.LteSimulation.PARAM_UL_PW]]
        power = config.simulation.get_uplink_power_from_parameters(parameters)
        config.simulation.set_uplink_tx_power(power)
        return 'OK'

    def set_downlink_rx_power(self, data):
        self._require_dict_keys(data, 'callbox', LteSimulation.LteSimulation.PARAM_DL_PW)
        config = self._get_callbox_config(data['callbox'])
        parameters = [LteSimulation.LteSimulation.PARAM_DL_PW, data[LteSimulation.LteSimulation.PARAM_DL_PW]]
        power = config.simulation.get_downlink_power_from_parameters(parameters)
        config.simulation.set_downlink_rx_power(power)
        return 'OK'

    def query_uplink_tx_power(self, data):
        self._require_dict_keys(data, 'callbox')
        config = self._get_callbox_config(data['callbox'])
        return { LteSimulation.LteSimulation.PARAM_UL_PW : config.simulation.get_uplink_tx_power()}

    def query_downlink_rx_power(self, data):
        self._require_dict_keys(data, 'callbox')
        config = self._get_callbox_config(data['callbox'])
        return { LteSimulation.LteSimulation.PARAM_DL_PW : config.simulation.get_downlink_rx_power()}

    def query_throughput(self, data):
        self._require_dict_keys(data, 'callbox')
        config = self._get_callbox_config(data['callbox'])
        return {
                'uplink' : config.simulation.maximum_uplink_throughput(),
                'downlink' : config.simulation.maximum_downlink_throughput()
                }

    def send_sms(self, data):
        self._require_dict_keys(data, 'callbox')
        config = self._get_callbox_config(data['callbox'])
        config.simulation.send_sms(data['sms'])
        return 'OK'

    def config_iperf(self, data):
        self._require_dict_keys(data, 'callbox')
        config = self._get_callbox_config(data['callbox'])
        config.iperf.configure(data)
        return 'OK'

    def start_iperf(self, data):
        self._require_dict_keys(data, 'callbox')
        config = self._get_callbox_config(data['callbox'])
        config.iperf.start()
        return 'OK'

    def stop_iperf(self, data):
        self._require_dict_keys(data, 'callbox')
        config = self._get_callbox_config(data['callbox'])
        config.iperf.stop()
        return 'OK'

    def close_iperf(self, data):
        self._require_dict_keys(data, 'callbox')
        config = self._get_callbox_config(data['callbox'])
        config.iperf.close()
        return 'OK'

    def query_iperf_results(self, data):
        self._require_dict_keys(data, 'callbox')
        config = self._get_callbox_config(data['callbox'])
        return config.iperf.query_results()

    def query_iperf_ip(self, data):
        self._require_dict_keys(data, 'callbox')
        config = self._get_callbox_config(data['callbox'])
        return {'ip' : config.iperf.ip_address}

    def _get_callbox_config(self, callbox, create_if_dne=False):
        if callbox not in self.configs_by_host:
            if create_if_dne:
                url = urllib.parse.urlsplit(callbox)
                if not url.hostname:
                    url = urllib.parse.urlsplit('//' + callbox)
                if not url.hostname:
                    raise ValueError(
                        f'Unable to parse callbox host: "{callbox}"')
                config = CallboxConfiguration()
                config.host = url.hostname
                config.port = 5025 if not url.port else url.port
                self.configs_by_host[callbox] = config
            else:
                raise ValueError(f'Callbox "{callbox}" not configured')
        return self.configs_by_host[callbox]

    @staticmethod
    def _require_dict_keys(d, *keys):
        for key in keys:
            if key not in d:
                raise Exception(f'Missing required data key "{key}"')

callbox_manager = CallboxManager()

path_lookup = {
        'config': callbox_manager.configure_callbox,
        'config/power/downlink' : callbox_manager.set_downlink_rx_power,
        'config/power/uplink' : callbox_manager.set_uplink_tx_power,
        'config/fetch/power/downlink' : callbox_manager.query_downlink_rx_power,
        'config/fetch/power/uplink' : callbox_manager.query_uplink_tx_power,
        'config/fetch/maxthroughput' : callbox_manager.query_throughput,
        'start': callbox_manager.begin_simulation,
        'sms': callbox_manager.send_sms,
        'iperf/config': callbox_manager.config_iperf,
        'iperf/start': callbox_manager.start_iperf,
        'iperf/stop': callbox_manager.stop_iperf,
        'iperf/close': callbox_manager.close_iperf,
        'iperf/fetch/result': callbox_manager.query_iperf_results,
        'iperf/fetch/ip': callbox_manager.query_iperf_ip,
}

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def entrypoint(path):
    try:
        return path_lookup[path](request.json)
    except Exception as e:
        return '%s:\n%s' % (e, traceback.format_exc()), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
