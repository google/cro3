#!/usr/bin/env python3

# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main file for pacina utility"""

import argparse
import contextlib
import json
import logging
import pathlib
import signal
import sys
import time
from typing import Optional
from typing import List
import urllib

import pandas as pd  # pylint: disable=import-error
import plotly.express  # pylint: disable=import-error
from pyftdi.ftdi import Ftdi  # pylint: disable=import-error
from pyftdi.i2c import I2cController  # pylint: disable=import-error

import cs_config
import cs_types
import cs_util

logger = logging.getLogger(__name__)

# Style for the DataFrame Table HTML generation
styles = [
    dict(selector="tr:hover", props=[("background-color", "#ffff99")]),
    dict(
        selector="",
        props=[
            ("border-collapse", "collapse"),
            ("width", "100%"),
            ("font-family", "sans-serif"),
        ],
    ),
    dict(
        selector="th",
        props=[
            ("font-size", "100%"),
            ("face", "Open Sans"),
            ("text-align", "left"),
            ("background-color", "#4a86e8"),
            ("color", "white"),
        ],
    ),
    dict(selector="caption", props=[("caption-side", "bottom")]),
]


class SignalHandler:
    """Signal Handler that sets a flag."""

    def __init__(self):
        self.terminate_signal = False
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, unused_frame):
        """Define a signal handler for record so we can stop on CTRL-C.

        Autotest can call subprocess.kill which will make us stop waiting and
        dump the rest of the log.
        """
        logger.warning("Signal handler called with signal %d", signum)
        self.terminate_signal = True

    def __bool__(self):
        return self.terminate_signal


def generate_reports(
    start_time,
    log_path,
    log_prefix,
    dut_info,
    data,
    avg_power,
    config_rails,
    power_state=None,
):
    header_record = [
        "time_abs",
        "time_relative",
        "rail",
        "accum",
        "count",
        "power",
    ]
    time_log_path = log_path / (log_prefix + "timeLog.csv")
    summary_path = log_path / (log_prefix + "summary.csv")
    summary_html_path = log_path / (log_prefix + "summary.html")

    df = pd.DataFrame(data, columns=header_record)
    df.to_csv(time_log_path)

    df_avg = pd.DataFrame.from_dict(avg_power, orient="index").reset_index()
    df_avg["power"] = df_avg["acc_power"] / df_avg["count"]
    df_avg.columns = [
        "Rail",
        "Total Accumulated (Raw)",
        "Count",
        "Accumulated Power",
        "Sense Resistor",
        "Average Power (W)",
    ]
    pd.options.display.float_format = "{:,.3f}".format

    df_avg = df_avg.sort_values(by=["Average Power (W)"], ascending=False)
    print(df_avg)
    df_avg.to_csv(summary_path)

    # Default Plots
    power_plots = []
    time_plot = plotly.express.line(
        df,
        x="time_relative",
        y="power",
        color="rail",
        labels={"power": "Power (w)", "time_relative": "Time (seconds)"},
    )
    time_plot.update_layout(
        title="Time Series",
        xaxis_title="Time (Seconds)",
        yaxis_title="Power (W)",
    )
    power_plots.append(time_plot)

    box_plot = plotly.express.box(df, y="power", x="rail")
    box_plot.update_layout(
        title="Measurement Statistics",
        xaxis_title="Rail",
        yaxis_title="Power (W)",
    )
    power_plots.append(box_plot)

    sdf_avg = df_avg.style.hide_index().set_table_styles(styles)

    if len(config_rails) > 0:
        rail_map = pd.DataFrame(config_rails)
        df_avg = pd.merge(df_avg, rail_map, on="Rail")
        df_avg["Average Power (W)"] = df_avg["Average Power (W)"].abs()
        df_avg["voltage (mV)"] = df_avg.Rail.apply(
            lambda x: x.split("_")[0].strip("PP")
        )
        star_plot = plotly.express.sunburst(
            df_avg,
            names="Rail",
            parents="Parent",
            values="Average Power (W)",
            title="Power Sunburst",
            color="voltage (mV)",
        )
        power_plots.append(star_plot)

        root_rail = "PPVAR_SYS"
        root_pwr = None
        if root_rail in df_avg.Rail.values:
            root_pwr = df_avg[df_avg.Rail == root_rail][
                "Average Power (W)"
            ].unique()[0]
        else:
            print(root_rail + " measurement not found.")

        t1_columns = ["Rail", "voltage (mV)", "Average Power (W)"]
        if root_rail in df_avg.Parent.values:
            t1_rails = df_avg[df_avg["Parent"] == root_rail]
            t1_pwr = t1_rails["Average Power (W)"].sum()
            print("Tier1 Summary")
            print(f"{'T1 Rail Total:':<20}{t1_pwr:>20.3f}")
            if root_pwr:
                print(f"{'T1 Root %s' % root_rail:<20}{root_pwr:>20.3f}")
                print(f"{'Root - T1 Total:':<20}{(root_pwr - t1_pwr):>20.3f}")

            print(t1_rails[t1_columns])

    with summary_html_path.open("w") as f:
        f.write("<h1>" + summary_html_path.name + "<h1>")
        if dut_info:
            test_info_path = log_path / (log_prefix + "test-info.json")
            stop_time = time.strftime("%Y-%m-%d %H:%M:%S")
            test_info = {}
            test_info["id"] = log_prefix
            test_info["measurement_phase"] = power_state
            test_info["measurement_start_time"] = time.strftime(
                "%Y%m%d %H%M%S", time.localtime(start_time)
            )
            test_info["measurement_stop_time"] = stop_time
            test_info = test_info | dut_info
            del test_info["configs"]
            del test_info["ftdi_urls"]

            df_test_info = (
                pd.DataFrame(test_info, index=[0]).transpose().reset_index()
            )
            df_test_info.columns = ["Items", "Test Config"]

            s = df_test_info.style.hide(axis="index").set_table_styles(styles)

            f.write(s.render())

            test_info["upload_data"] = True
            with open(test_info_path, "w") as fjson:
                json.dump(test_info, fjson, indent=2, separators=(",", ": "))

        f.write(sdf_avg.render())
        for pplts in power_plots:
            f.write(
                pplts.to_html(
                    full_html=False,
                    include_plotlyjs="cdn",
                    default_height="50%",
                )
            )
    print(
        f"Report: file://{urllib.parse.quote(str(summary_html_path.absolute()))}"
    )


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-s",
        "--single",
        help=(
            "Use to take a single voltage, current "
            " power measurement of all rails"
        ),
        action="store_true",
    )
    parser.add_argument(
        "-t", "--time", default=10, help="Time to capture in seconds"
    )
    parser.add_argument(
        "--configs",
        nargs="*",
        default=[],
        help=(
            "Current sensor configuration files. "
            "Supports both servod and pacman formats. "
            "Number of config files needs to match number of "
            "number of FTDI URLs."
        ),
    )
    parser.add_argument(
        "--power_state",
        default="undefined",
        choices=[
            "undefined",
            "z5",
            "z2",
            "z1",
            "s5",
            "s4",
            "s3",
            "s0ix",
            "plt-1h",
            "plt-10h",
        ],
        help=("Power State Information"),
    )
    parser.add_argument(
        "-O",
        "--output",
        type=pathlib.Path,
        default="./results",
        help="Path for log files",
    )
    parser.add_argument(
        "-p",
        "--polarity",
        type=cs_types.Polarity,
        default=cs_types.Polarity.UNIPOLAR,
        choices=cs_types.Polarity,
        help="Measurements can either be unipolar or bipolar",
    )
    parser.add_argument(
        "--ftdi-urls",
        nargs="*",
        default=["ftdi:///"],
        help=(
            "FTDI URLs. Number of URLs needs to match number of config files"
        ),
    )
    parser.add_argument(
        "--dut-info",
        type=argparse.FileType("r"),
        help="JSON file containing DUT related information",
    )
    parser.add_argument(
        "--dut",
        default="",
        help="Target DUT. Only used when --dut_info is used.",
    )
    parser.add_argument(
        "--sample-time",
        default=1,
        type=float,
        help="Target sample time in seconds",
    )
    parser.add_argument(
        "-d",
        "--debug",
        help="Print debug messages",
        action="store_const",
        dest="loglevel",
        const=logging.DEBUG,
        default=logging.WARNING,
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Print verbose messages",
        action="store_const",
        dest="loglevel",
        const=logging.INFO,
    )

    return parser.parse_args(argv)


@contextlib.contextmanager
def managed_ftdi(ftdi_url):
    """Managed FTDI resource."""
    ftdi_inst = I2cController()
    ftdi_inst.configure(ftdi_url)
    try:
        yield ftdi_inst
    finally:
        ftdi_inst.close()


def log_power_continuous(log_duration, sample_time, configs):
    logger.info("Measuring Power for %ss.", log_duration)
    terminate_signal = SignalHandler()

    stime = time.time()
    timeout = stime + float(log_duration)

    # Current sensors get reset by the first read (setting t=0)
    tprev_sample = 0
    sample_index = 0
    while True:
        tcur_sample = time.time()
        if tcur_sample > timeout:
            if sample_index > 1:
                break
        else:
            if tprev_sample == 0:
                tprev_sample = tcur_sample
            elif tcur_sample - tprev_sample < sample_time:
                continue
            else:
                tprev_sample = tcur_sample
        if terminate_signal:
            break
        print(
            "Logging: %.2f / %.2f s..."
            % (tcur_sample - stime, float(log_duration)),
            end="\r",
        )

        # Depending on the system, it takes ~150ms to read 4 ch.
        # This results in second FTDI bus to have more samples than the sampling
        # time.
        for config in configs:
            config.log_continuous()
        sample_index = sample_index + 1


def log_power_single(configs, log_path, log_prefix):
    header_single = ["Rail", "Voltage (V)", "Current (A)", "Power (W)"]
    data = []
    gpio_data = []
    logger.info(
        ("Taking a single voltage, current " "power measurement of all rails")
    )

    for config in configs:
        config.log_single()

    single_log_path = log_path / (log_prefix + "singleLog.csv")
    for config in configs:
        data.extend(config.data)
        if config.gpio_vals:
            gpio_data.extend(config.gpio_vals)
    df = pd.DataFrame(data, columns=header_single)

    pd.options.display.float_format = "{:,.3f}".format
    print(df)
    df.to_csv(single_log_path)

    if gpio_data:
        df_gpio = pd.DataFrame(gpio_data, columns=["GPIO", "State"])
        print("\nGPIO States")
        print(df_gpio)

    logger.info("Output written to %s", single_log_path)


def main(argv: Optional[List[str]] = None) -> Optional[int]:

    args = parse_args(argv)

    logging.basicConfig(level=args.loglevel)

    # Adding PacDebugger V1 VID PID
    Ftdi.add_custom_vendor(0x18D1, "Google")
    Ftdi.add_custom_product(0x18D1, 0x5211, "PacDebuggerV1")
    ftdis = Ftdi.list_devices()
    if len(ftdis) == 0:
        logger.error("No FTDIs found. Aborting!")
        return

    start_time = time.time()

    dut_info = None
    log_prefix = ""

    if args.dut_info and not args.dut:
        logger.error("Specify target DUT.")
        return
    elif args.dut_info and args.dut:
        dut_info = json.load(args.dut_info)
        if args.dut not in dut_info.keys():
            logger.error(args.dut + " not found in " + args.dut_info.name)
            return
        dut_info = dut_info[args.dut]
        args.ftdi_urls = dut_info["ftdi_urls"]
        args.configs = dut_info["configs"]
        log_prefix = "_".join(
            [
                dut_info["model"],
                dut_info["build_phase"],
                dut_info["sku"],
                dut_info["dut_id"],
                dut_info["os_version"],
                args.power_state,
                time.strftime("%Y%m%d_%H%M%S", time.localtime(start_time)),
            ]
        )
        log_prefix = log_prefix + "_"

    if not args.configs:
        logger.error("Current Sensor Configuration(s) Required")
        return

    if len(args.ftdi_urls) != len(args.configs):
        logger.error(
            "Number of config files needs to match number of FTDI URLs"
        )
        return

    for ftdi_url in args.ftdi_urls:
        Ftdi.get_device(ftdi_url)

    # Prepare output directory.

    if log_prefix:
        log_path = args.output / dut_info["program"]
    else:
        log_path = args.output / time.strftime(
            "%Y%m%d_%H%M%S", time.localtime(start_time)
        )

    log_path.mkdir(parents=True, exist_ok=True)

    # based on the config files, generate cs instances
    configs = []
    config_rails = []

    with contextlib.ExitStack() as stack:
        for ftdi_url, input_config in zip(args.ftdi_urls, args.configs):
            logger.info(
                "Measuring power from " + ftdi_url + " using " + input_config
            )
            ftdi = stack.enter_context(managed_ftdi(ftdi_url))
            config = cs_config.BusConfig(
                input_config,
                ftdi,
                cs_util.supported_pns,
                polarity=args.polarity,
                sample_time=args.sample_time,
            )

            configs.append(config)
            config_rails.extend(config.rails)

        if args.single:
            log_power_single(configs, log_path, log_prefix)
            return

        log_power_continuous(args.time, args.sample_time, configs)

    logger.info("Completed Logging")
    avg_power = {}
    data = []

    for config in configs:
        data.extend(config.get_acc_pwr())
        avg_power = {**avg_power, **config.get_avg_pwr()}

    generate_reports(
        start_time,
        log_path,
        log_prefix,
        dut_info,
        data,
        avg_power,
        config_rails,
        args.power_state,
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
