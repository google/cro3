#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main file for pacman utility"""

from argparse import ArgumentParser
from argparse import FileType
import datetime
import os
import pathlib
from sys import modules
from sys import stderr

import pac_utils
import pacboard
import pacconfig
import pandas
import plotly.express


def main():
    """main function"""
    polarity_default = 'bipolar'

    argparser = ArgumentParser(description=modules[__name__].__doc__)
    argparser.add_argument(
        '-s',
        '--single',
        help=
        'Use to take a single voltage, current,'\
            ' power measurement of all rails and report GPIO status',
        action='store_true')
    argparser.add_argument('-t',
                           '--time',
                           default=9999999,
                           help='Time to capture in seconds')
    argparser.add_argument(
        '-c',
        '--config',
        type=pathlib.Path,
        help='PAC address and configuration file used by servod')
    argparser.add_argument(
        '-O',
        '--output',
        nargs='?',
        default=os.path.join(
            './Data',
            datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')),
        help='Path for log files')
    argparser.add_argument(
        '-p',
        '--polarity',
        default=polarity_default,
        help='Measurements can either be unipolar or bipolar')

    args = argparser.parse_args()

    if not args.config:
        print('PAC Configuration Required')
        return False

    # Store everything in output folder.
    log_path = args.output
    single_log_path = os.path.join(log_path, 'singleLog.csv')
    time_log_path = os.path.join(log_path, 'timeLog.csv')
    accumulator_log_path = os.path.join(log_path, 'accumulatorData.csv')
    report_log_path = os.path.join(log_path, 'report.html')
    pathlib.Path(log_path).mkdir(parents=True, exist_ok=True)

    # Load board config
    print(args.config)
    config = pacconfig.PacConfig(args.config)

    # Register the custom VID:PID used for provisioned PACDebuggers
    pacboard.PacDebugger.configure_custom_devices()

    # If single, take a single shot of these measurements then quit.
    # Print which files are being used for clarity
    if args.single:
        print(
            'Taking a single voltage, current, '\
                'power measurement of all rails and reporting GPIO status'
        )

        log = pac_utils.query_all(config, polarity=args.polarity)
        log.to_csv(single_log_path)
        return False

    # Else we're going to take a time log.
    # Print which files are being used for clarity
    print('Taking an extended reading')

    # Record the sample and log to file.
    (log, accumulator_log) = pac_utils.record(config,
                                              record_length=args.time,
                                              polarity=args.polarity)
    log.to_csv(time_log_path)
    accumulator_log.to_csv(accumulator_log_path)

    # Generate plots using plotly.
    time_plot = plotly.express.line(log,
                                    x='relativeTime',
                                    y='power',
                                    color='rail',
                                    labels={
                                        'power': 'Power (w)',
                                        'relativeTime': 'Time (seconds)'
                                    })
    time_plot.update_layout(
        title='Time Series',
        xaxis_title='Time (Seconds)',
        yaxis_title='Power (W)',
    )
    box_plot = plotly.express.box(log, y='power', x='rail')
    box_plot.update_layout(title='Instaneous Measurement Statistics',
                           xaxis_title='Rail',
                           yaxis_title='Power (W)')
    accumulator_log = accumulator_log.sort_values(by='Average Power (w)',
                                                  ascending=False)
    summary_table = plotly.graph_objects.Figure(data=[
        plotly.graph_objects.Table(
            header=dict(values=[
                'Rail', 'Accumulation Time (s)', 'Sense Resistor (Ohm)',
                'Average Power (W)'
            ],
                        align='left'),
            cells=dict(values=[
                accumulator_log.Rail,
                accumulator_log.tAccum.round(2), accumulator_log.rSense,
                accumulator_log['Average Power (w)'].round(3)
            ],
                       align='left'))
    ])

    summary_table.update_layout(title='Accumulator Measurements')
    if len(config.rails) > 0:
        mapping = []
        for rail in config.rails:
            mapping.append({'Rail': rail.rail, 'Parent': rail.parent})

        skip_sunplot = False
        mapping = pandas.DataFrame(mapping)
        accumulator_log = pandas.merge(accumulator_log, mapping, on='Rail')
        # Bidirectional Values means powers can be negative
        avg_power = accumulator_log['Average Power (w)'].abs()
        accumulator_log['Average Power (w)'] = avg_power
        # Voltage column used for color coding
        accumulator_log['voltage (mv)'] = accumulator_log.Rail.apply(
            lambda x: x.split('_')[0].strip('PP')
        )
        star_plot = plotly.express.sunburst(accumulator_log,
                                            names='Rail',
                                            parents='Parent',
                                            values='Average Power (w)',
                                            title='Power Sunburst',
                                            color='voltage (mv)')
    else:
        print('Skipping Sunplot')
        skip_sunplot = True
    # Generate an HTML Report.
    with open(report_log_path, 'w') as f:
        f.write(summary_table.to_html(full_html=False, include_plotlyjs='cdn'))
        if not skip_sunplot:
            f.write(star_plot.to_html(full_html=False, include_plotlyjs='cdn'))
        f.write(box_plot.to_html(full_html=False, include_plotlyjs='cdn'))
        f.write(time_plot.to_html(full_html=False, include_plotlyjs='cdn'))


if __name__ == '__main__':
    try:
        main()
    except Exception as exception:
        print(str(exception), file=stderr)
