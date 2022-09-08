#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""Main file for pacman utility"""

from argparse import ArgumentParser
import datetime
import os
import pathlib
import sys
from sys import modules
import urllib

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
    argparser.add_argument('--sample_time',
                           default=1,
                           type=float,
                           help='Sample time in seconds')
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
    argparser.add_argument(
        '-d',
        '--device',
        default='',
        help='Serial number of provisioned pacdebugger to use'
    )

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

    # See if we've been passed a serial number to use
    ftdi_url = 'ftdi:///'
    if args.device != '':
        ftdi_url = pacboard.PacDebugger.url_by_serial(args.device)

        if ftdi_url == '':
            print(f'Failed to find Pacdebugger with serial {args.device}',
                file=sys.stderr)
            return False


    # If single, take a single shot of these measurements then quit.
    # Print which files are being used for clarity
    if args.single:
        print(
            'Taking a single voltage, current, '\
                'power measurement of all rails and reporting GPIO status'
        )

        log = pac_utils.query_all(config, ftdi_url=ftdi_url,
            polarity=args.polarity)
        log.to_csv(single_log_path)
        return False

    # Else we're going to take a time log.
    # Print which files are being used for clarity
    print('Taking an extended reading')

    # Record the sample and log to file.
    (log, accumulator_log) = pac_utils.record(config,
                                              ftdi_url=ftdi_url,
                                              record_length=args.time,
                                              polarity=args.polarity,
                                              sample_time=args.sample_time)
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
            lambda x: x.split('_')[0].strip('PP'))
        star_plot = plotly.express.sunburst(accumulator_log,
                                            names='Rail',
                                            parents='Parent',
                                            values='Average Power (w)',
                                            title='Power Sunburst',
                                            color='voltage (mv)')
        # Calculate what the sum of the child rails of root is
        root = 'PPVAR_SYS'
        root_pwr = accumulator_log[accumulator_log.Rail ==
                                   root]['Average Power (w)']
        # This should be a single element
        root_pwr = root_pwr.iloc[0]
        # tier 1 rails, children of root
        t1_rails = accumulator_log[accumulator_log['Parent'] == 'PPVAR_SYS']
        summary_columns = ['Rail', 'voltage (mv)', 'Average Power (w)']
        t1_pwr = t1_rails['Average Power (w)'].sum()
        t1_summary = t1_rails[summary_columns]
        t1_summary_text = (
            f"{'T1 Rail Total:':<20}{t1_pwr:>20.3f}" + '\n' +
            f"{'T1 Root %s' % root:<20}{root_pwr:>20.3f}" + '\n' +
            f"{'Root - T1 Total:':<20}{(root_pwr - t1_pwr):>20.3f}" + '\n')
        print('Tier1 Summary')
        print(t1_summary_text)
        print(t1_summary)

        # HTML summary table
        t1_summary_table = plotly.graph_objects.Figure(data=[
            plotly.graph_objects.Table(
                header=dict(values=summary_columns, align='left'),
                cells=dict(values=[
                    t1_summary.Rail, t1_summary['voltage (mv)'],
                    t1_summary['Average Power (w)'].round(3)
                ],
                           align='left'))
        ])
        t1_summary_table.update_layout(
            title=f"{'T1 Rail Total: %.3f Watts' % t1_pwr:6>}")
    else:
        print('Skipping Sunplot')
        skip_sunplot = True
    # Generate an HTML Report.
    with open(report_log_path, 'w') as f:
        f.write(summary_table.to_html(full_html=False, include_plotlyjs='cdn'))
        if not skip_sunplot:
            f.write(
                t1_summary_table.to_html(full_html=False,
                                         include_plotlyjs='cdn',
                                         default_width='100%',
                                         default_height='50%'))
            f.write(star_plot.to_html(full_html=False, include_plotlyjs='cdn'))
        f.write(box_plot.to_html(full_html=False, include_plotlyjs='cdn'))
        f.write(time_plot.to_html(full_html=False, include_plotlyjs='cdn'))

        # Use PWD if available to avoid de-referencing symlinks otherwise use
        # CWD
        full_path = os.path.join(
            os.getenv('PWD') or os.getcwd(), report_log_path)
        full_path = os.path.normpath(full_path)

        print(f'Report: file://{urllib.parse.quote(full_path)}')

    return True


if __name__ == '__main__':
    main()
