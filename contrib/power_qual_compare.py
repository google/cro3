#!/usr/bin/env python3
"""Read two test logs and report differences in power consumption."""
# Copyright 2022 The Chromium OS Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Parse logs of 2 runs of PowerQual.full and compare them printing problems.
# Based on a script by jacobraz@google.com

# Additions:
# - Collect energy ratings and compare
import os
import sys
import time
import json
from pathlib import Path
from io import StringIO
# pylint: disable=import-error
from colorama import Fore, Style

SUBSYSTEMS = ['PL1', 'uncore', 'dram', 'core', 'package-0', 'psys']
ENERGY_RATINGS = ['w_energy_rate', 'wh_energy_used']
def get_subsystem(val):
    """Return valid subsystem from given string or None."""
    for s in SUBSYSTEMS:
        if s in val:
            return s

    return None

def get_energy_metric(name):
    """Return valid energy metric or None."""
    if name in ENERGY_RATINGS:
        return name
    return None

def color_number(value):
    """Return the number as a string with color formatting"""
    if value == 'NA' or value < 0:
        color = Fore.RED
    else:
        color = Fore.GREEN
    return (color + '{}' + Style.RESET_ALL).format(value)

def get_test_name(fname):
    """Read the test name from the JSON file, if we can find it."""
    json_file = Path(os.path.join(os.path.dirname(fname), 'results.json'))
    if not json_file.exists():
        return ''
    try:
        results = json.loads(open(json_file).read())
        return results['tests'][0]['testname']
    # pylint: disable=broad-except
    except Exception:
        return ''

def read_report(fname):
    """Read a test log and return a dictionary of metrics.

    There are two kinds of allowed  metrics:
    - A set of subsystems
    - A set of energy usage metrics
    The returned dictionary will have keys for both, if they are present
    in the log.
    """
    def is_float(val):
        try:
            float(val)
            return True
        except ValueError:
            return False

    def is_valid_name(subsystem, metric):
        if subsystem is None:
            return False
        if get_energy_metric(metric):
            return True

        if 'temp' in metric:
            return False
        if 'avg' in metric:
            return True

        return False

    metrics = {}
    with open(fname, 'r') as results:
        for line in results.readlines():
            if not line:
                break
            arr = line.split()
            if not (len(arr) == 3 and is_float(arr[2])):
                continue
            metric_name = arr[1]
            if get_subsystem(metric_name):
                subsys_name = get_subsystem(metric_name)
            else:
                subsys_name = get_energy_metric(metric_name)
            if not is_valid_name(subsys_name, metric_name):
                # ignore max min std cnt and temperature measurements
                continue
            metrics[metric_name] = float(arr[2])
    return metrics


def main():
    """Read the files and create the report."""
    usage = """./power_qual_compare.py /path/to/old-result/test_report.log
            /path/to/kernelnext-result/test_report.log"""
    if len(sys.argv) != 3:
        print(usage)
        sys.exit(0)

    old_file = sys.argv[1]
    new_file = sys.argv[2]

    metric_diffs = {}
    subsys_diffs = {s:[] for s in SUBSYSTEMS}

    test_name = get_test_name(new_file)
    metrics_old = read_report(old_file)
    metric_diffs = dict(metrics_old)
    metrics_new = read_report(new_file)

    for metric_name, new_val in metrics_new.items():
        if metric_name not in metric_diffs:
            continue
        metric_diffs[metric_name] -= new_val
        subsys_name = get_subsystem(metric_name)
        if subsys_name is None:
            continue
        if new_val != 0:
            subsys_diffs[subsys_name].append(metric_diffs[metric_name]/new_val)
        elif metric_diffs[metric_name] != 0:
            # there is a difference but cant divide by kn value since its 0
            # use 100% change if one value is 0
            subsys_diffs[subsys_name].append(100)

    # Compute differences in w_energy_rate and wh_energy_used
    try:
        wer_diff = metrics_old['w_energy_rate'] - metrics_new['w_energy_rate']
    except KeyError:
        # In case w_energy_rate is missing in either report
        wer_diff = 'NA'

    try:
        whe_diff = metrics_old['wh_energy_used'] - metrics_new['wh_energy_used']
    except KeyError:
        # In case w_energy_rate is missing in either report
        whe_diff = 'NA'

    def summary_print(buf, format_fn):
        # if the diff is negative, the kernel-next used more power
        buf.write(f'******************* Test: {test_name} ')
        buf.write('ENERGY RATINGS ********************\n')
        buf.write('w_energy_rate difference: ' + format_fn(wer_diff) + '\n')
        buf.write('wh_energy_used difference: ' + format_fn(whe_diff) + '\n')
        buf.write(f'******************* Test: {test_name} ')
        buf.write('SUB SYSTEMS************************\n')
        buf.write('Average percent change in each subsystem ')
        buf.write('(Positive values indicate better performance)\n')
        for subsys in SUBSYSTEMS:
            if len(subsys_diffs[subsys]) == 0:
                continue
            buf.write(subsys)
            buf.write(': ')
            avg_percent_diff = (sum(subsys_diffs[subsys])/
                                len(subsys_diffs[subsys])*100)
            buf.write(format_fn(avg_percent_diff))
            buf.write('\n')


    summarybuf = StringIO()
    # Print a summary of statistic to standard out
    summary_print(summarybuf, color_number)

    print(summarybuf.getvalue())

    # Dump summary to file as well
    suffix = test_name + '_' + str(int(time.time())) + '.txt'
    with open('summary_' + suffix, 'w') as summary:
        summary_print(summary, str)

    with open('diffs_' + suffix, 'w') as diffs:
        diffs.write('Diff of each individual metric:\n')
        for metric in list(metric_diffs.keys()):
            diffs.write(metric)
            diffs.write(': ')
            diffs.write(str(metric_diffs[metric]))
            diffs.write('\n')


if __name__ == '__main__':
    main()
