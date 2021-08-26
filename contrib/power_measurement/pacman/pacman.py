#!/usr/bin/python3
# -*- coding: utf-8 -*-

# Copyright 2021 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from argparse import ArgumentParser, FileType
from sys import modules, stderr
import datetime
import os
from pathlib import Path
import pac_utils
import pandas
import plotly.express

def main():
    argparser = ArgumentParser(description=modules[__name__].__doc__)
    argparser.add_argument(
        '-s',
        '--single',
        help=
        'Use to take a single voltage, current, power measurement of all rails',
        action="store_true")
    argparser.add_argument(
        '-t',
        '--time',
        default=1,
        help='Time to capture in seconds')
    argparser.add_argument(
        '-c',
        '--config',
        type=FileType('r'),
        help='PAC address and configuration file used by servod')
    argparser.add_argument(
        '-O',
        '--output',
        nargs='?',
        default=os.path.join('./Data', datetime.datetime.now().strftime('%Y-%m-%dT%H:%M:%S')),
        help='Path for log files')
    argparser.add_argument(
        '-m',
        '--mapping',
        type=FileType('r'),
        default='./GuybrushProto0_RailMapping.csv',
        help='Rail hierachy mapping used to generate sunburst plot')
    argparser.add_argument(
        '-g',
        '--gpio',
        type=FileType('r'),
        default='./guybrush_r0_pacs_mainsmt_gpio.csv',
        help='PAC address to GPIO Rail mapping')

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
    Path(log_path).mkdir(parents=True, exist_ok=True)

    # If single, take a single shot of these measurements then quit.
    if args.single:
        log = pac_utils.query_all(args.config.name, args.gpio.name)
        log.to_csv(single_log_path)
        return False

    # Else we're going to take a time log.
    # Record the sample and log to file.
    (log, accumulator_log) = pac_utils.record(args.config.name,
                                   rail=['all'],
                                   record_length=args.time)
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
    summary_table = plotly.graph_objects.Figure(
        data=[
            plotly.graph_objects.Table(
                header=dict(values=['Rail',
                                    'Accumulation Time (s)',
                                    'Sense Resistor (Ohm)',
                                    'Average Power (W)'],
                                    align='left'),
                cells=dict(values=[
                    accumulator_log.Rail,
                    accumulator_log.tAccum.round(2), accumulator_log.rSense,
                    accumulator_log['Average Power (w)'].round(3)
                 ], align='left'))
        ]
    )
    summary_table.update_layout(title='Accumulator Measurements')

    if args.mapping is not None:
        skip_sunplot = False
        mapping = pandas.read_csv(args.mapping, skiprows=4)
        accumulator_log = pandas.merge(accumulator_log, mapping, on='Rail')
        star_plot = plotly.express.sunburst(accumulator_log,
                               names='Rail',
                               parents='Parent',
                               values='Average Power (w)',
                               title='Power Sunburst')
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
