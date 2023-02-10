# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Proxy server for configuring callboxes."""

import traceback
import urllib

from cellular import handover_simulator as hs
from cellular.callbox_utils import cmw500_cellular_simulator as cmw
from cellular.callbox_utils.cmw500_handover_simulator import (
    Cmw500HandoverSimulator,
)
from cellular.simulation_utils import BaseCellConfig
from cellular.simulation_utils import ChromebookCellularDut
from cellular.simulation_utils import CrOSLteSimulation
import flask  # pylint: disable=E0401
from flask import request  # pylint: disable=E0401


app = flask.Flask(__name__)
app.config["DEBUG"] = False


class CallboxConfiguration:
    """Callbox access configuration."""

    def __init__(self):
        self.host = None
        self.port = None
        self.dut = None
        self.simulator = None
        self.simulation = None
        self.parameters = None
        self.iperf = None
        self.tx_measurement = None
        self.technology = None
        self.handover = None

    def require_simulation(self):
        """Verifies that CellularSimulator controls are available for the current callbox configuration.

        Raises:
            ValueError: If the feature is not supported for the current callbox configuration.
        """
        if self.simulation is None or self.simulator is None:
            raise ValueError(
                "Action not supported for RAT: {self.technology} in the current callbox configuration"
            )

    def require_iperf(self):
        """Verifies that Iperf measurements are available for the current callbox configuration.

        Raises:
            ValueError: If the feature is not supported for the current callbox configuration.
        """
        if self.simulation is None:
            raise ValueError(
                "Iperf not supported for RAT: {self.technology} in the current callbox configuration"
            )

    def require_tx_measurement(self):
        """Verifies that tx measurements are available for the current callbox configuration.

        Raises:
            ValueError: If the feature is not supported for the current callbox configuration.
        """
        if self.simulation is None:
            raise ValueError(
                "Tx measurement not supported for RAT: {self.technology} in the current callbox configuration"
            )


class CallboxManager:
    """Manager object that holds configurations to known callboxes."""

    def __init__(self):
        self.configs_by_host = dict()

    def configure_callbox(self, data):
        self._require_dict_keys(data, "callbox", "hardware", "cellular_type")
        config = self._get_callbox_config(data["callbox"], True)
        config.technology = hs.CellularTechnology(data["cellular_type"])
        if data["hardware"] == "CMW":
            config.simulator = cmw.CMW500CellularSimulator(
                config.host, config.port
            )
            config.handover = Cmw500HandoverSimulator(config.simulator.cmw)
            config.iperf = config.simulator.cmw.init_perf_measurement()
            config.tx_measurement = config.simulator.cmw.init_lte_measurement()
            config.simulator.cmw.stop_all_signalling()
        else:
            raise Exception(f'Unsupported hardware: {data["hardware"]}')

        config.dut = ChromebookCellularDut.ChromebookCellularDut(
            "no_dut_connection", app.logger
        )
        if data["cellular_type"] == "LTE":
            config.simulation = CrOSLteSimulation.CrOSLteSimulation(
                config.simulator,
                app.logger,
                config.dut,
                {"attach_retries": 1, "attach_timeout": 120},
                None,
            )
        else:
            raise Exception(f'Unsupported RAT: {data["cellular_type"]}')

        # backwards compatibility, configuration options were changed
        # from a list to a dictionary
        if "parameter_list" in data:
            params = data["parameter_list"]
            config.parameters = {
                params[i]: params[i + 1] for i in range(0, len(params), 2)
            }
        elif "configuration" in data:
            config.parameters = data["configuration"]
        else:
            raise Exception(
                "Missing required argument, either "
                '"configuration" or "parameter_list" must be defined'
            )

        # Stop any existing connection before configuring as some configuration
        # items cannot be adjusted while the UE is attached.
        config.simulation.stop()
        config.simulation.configure(config.parameters)
        config.simulator.wait_until_quiet()
        config.simulation.setup_simulator()
        return "OK"

    def begin_simulation(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_simulation()
        config.simulation.start()
        config.simulator.wait_until_quiet()
        return "OK"

    def set_uplink_tx_power(self, data):
        self._require_dict_keys(
            data, "callbox", BaseCellConfig.BaseCellConfig.PARAM_UL_PW
        )
        config = self._get_callbox_config(data["callbox"])
        config.require_simulation()
        parameters = {
            BaseCellConfig.BaseCellConfig.PARAM_UL_PW: data[
                BaseCellConfig.BaseCellConfig.PARAM_UL_PW
            ]
        }
        power = config.simulation.get_uplink_power_from_parameters(parameters)

        config.simulation.set_uplink_tx_power(power)
        config.simulator.wait_until_quiet()
        return "OK"

    def set_downlink_rx_power(self, data):
        self._require_dict_keys(
            data, "callbox", BaseCellConfig.BaseCellConfig.PARAM_DL_PW
        )
        config = self._get_callbox_config(data["callbox"])
        config.require_simulation()
        parameters = {
            BaseCellConfig.BaseCellConfig.PARAM_DL_PW: data[
                BaseCellConfig.BaseCellConfig.PARAM_DL_PW
            ]
        }
        power = config.simulation.get_downlink_power_from_parameters(parameters)
        config.simulation.set_downlink_rx_power(power)
        return "OK"

    def query_uplink_tx_power(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_simulation()
        return {
            BaseCellConfig.BaseCellConfig.PARAM_UL_PW: config.simulation.get_uplink_tx_power()
        }

    def query_downlink_rx_power(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_simulation()
        return {
            BaseCellConfig.BaseCellConfig.PARAM_DL_PW: config.simulation.get_downlink_rx_power()
        }

    def query_throughput(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_simulation()
        return {
            "uplink": config.simulation.maximum_uplink_throughput(),
            "downlink": config.simulation.maximum_downlink_throughput(),
        }

    def send_sms(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_simulation()
        config.simulation.send_sms(data["sms"])
        return "OK"

    def configure_iperf(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_iperf()
        config.iperf.configure(data)
        return "OK"

    def start_iperf(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_iperf()
        config.iperf.start()
        return "OK"

    def stop_iperf(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_iperf()
        config.iperf.stop()
        return "OK"

    def close_iperf(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_iperf()
        config.iperf.close()
        return "OK"

    def query_iperf_results(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_iperf()
        return config.iperf.query_results()

    def query_iperf_ip(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_iperf()
        return {"ip": config.iperf.ip_address}

    def configure_uplink_measurement(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        sample_count = data.get("sample_count", 100)
        config.require_tx_measurement()
        config.tx_measurement.sample_count = sample_count
        return "OK"

    def run_uplink_measurement(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_tx_measurement()
        config.tx_measurement.run_measurement()
        return "OK"

    def query_uplink_measurement(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_tx_measurement()
        meas = config.tx_measurement
        return {
            "average": meas.tx_average,
            "min": meas.tx_min,
            "max": meas.tx_max,
            "stdev": meas.tx_stdev,
        }

    def stop_uplink_measurement(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_tx_measurement()
        config.tx_measurement.stop_measurement()
        return "OK"

    def close_uplink_measurement(self, data):
        self._require_dict_keys(data, "callbox")
        config = self._get_callbox_config(data["callbox"])
        config.require_tx_measurement()
        config.tx_measurement.abort_measurement()
        return "OK"

    def handover(self, data):
        self._require_dict_keys(data, "callbox", "band", "channel")
        config = self._get_callbox_config(data["callbox"])

        # If technology not defined, then treat as intra-RAT
        technology = (
            hs.CellularTechnology(data["technology"])
            if "technology" in data
            else config.technology
        )

        # NOTE: treating LTE as default and do not wipe config simulation/measurement items.
        # TODO: For CMX/5G(b/262286938), revisit this and move logic to switch between technologies into
        # the configuration object itself.
        if technology == hs.CellularTechnology.LTE:
            self._require_dict_keys(data, "bw")
            config.handover.lte_handover(
                data["band"], data["channel"], data["bw"], config.technology
            )
        elif technology == hs.CellularTechnology.WCDMA:
            # simulation and measurement items are unsupported for WCDMA,
            # handovers can still be performed, but returning to LTE will
            # not restore them until configure_callbox is called again.
            config.simulator = None
            config.simulation = None
            config.iperf = None
            config.tx_measurement = None
            config.handover.wcdma_handover(
                data["band"], data["channel"], config.technology
            )
        else:
            raise ValueError(
                f"Unsupported handover destination technology {technology}"
            )

        config.technology = technology
        return "OK"

    def _get_callbox_config(self, callbox, create_if_dne=False):
        if callbox not in self.configs_by_host:
            if create_if_dne:
                url = urllib.parse.urlsplit(callbox)
                if not url.hostname:
                    url = urllib.parse.urlsplit("//" + callbox)
                if not url.hostname:
                    raise ValueError(
                        f'Unable to parse callbox host: "{callbox}"'
                    )
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
    "config": callbox_manager.configure_callbox,
    "config/power/downlink": callbox_manager.set_downlink_rx_power,
    "config/power/uplink": callbox_manager.set_uplink_tx_power,
    "config/fetch/power/downlink": callbox_manager.query_downlink_rx_power,
    "config/fetch/power/uplink": callbox_manager.query_uplink_tx_power,
    "config/fetch/maxthroughput": callbox_manager.query_throughput,
    "start": callbox_manager.begin_simulation,
    "sms": callbox_manager.send_sms,
    "iperf/config": callbox_manager.configure_iperf,
    "iperf/start": callbox_manager.start_iperf,
    "iperf/stop": callbox_manager.stop_iperf,
    "iperf/close": callbox_manager.close_iperf,
    "iperf/fetch/result": callbox_manager.query_iperf_results,
    "iperf/fetch/ip": callbox_manager.query_iperf_ip,
    "txmeas/config": callbox_manager.configure_uplink_measurement,
    "txmeas/run": callbox_manager.run_uplink_measurement,
    "txmeas/stop": callbox_manager.stop_uplink_measurement,
    "txmeas/close": callbox_manager.close_uplink_measurement,
    "txmeas/fetch/result": callbox_manager.query_uplink_measurement,
    "handover": callbox_manager.handover,
}


@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def entrypoint(path):
    try:
        return path_lookup[path](request.json)
    except Exception as e:
        return "%s:\n%s" % (e, traceback.format_exc()), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
