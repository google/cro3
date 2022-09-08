#!/usr/bin/env python3
# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.
"""
Usage: add_header.py base/filename.h platform2/code.cc

Add base/filename.h header into platform2/code.cc.
The code will try to put at best location, but there's not guarantee. Manual
review is required before submission.
"""

import sys
import re

# Directories for libchrome header includes.
# brillo is added here since developers usually include in the same section with
# libchrome though brillo is not part of libchrome
LIBCHROME_DIRS = 'base|brillo|dbus|mojo'


def get_include_range(lines):
    begin = -1
    for idx, line in enumerate(lines):
        if line.startswith('#include'):
            begin = idx
            break
    if begin == -1:
        return -1, -1

    end = -1
    for idx, line in enumerate(lines[begin:], start=begin):
        # Skip empty lines since #include may be separated to multiple parts for
        # readability.
        if not line.strip():
            continue
        if not line.startswith('#include'):
            end = idx
            break
    assert end > begin

    return (begin, end)


def get_libchrome_include_range(lines, libchrome_pattern):
    begin = -1
    for idx, line in enumerate(lines):
        if libchrome_pattern.match(line):
            begin = idx
            break
    if begin == -1:
        return -1, -1

    end = -1
    for idx, line in enumerate(lines[begin:], start=begin):
        if not libchrome_pattern.match(line):
            end = idx
            break
    assert end > begin

    return (begin, end)


def main(header, filename):
    with open(filename) as f:
        lines = f.readlines()

    if header.startswith('<') or header.startswith('"'):
        line_to_add = '#include %s\n' % (header)
        open_symbol, close_symbol = header[0], header[-1]
    else:
        line_to_add = '#include <%s>\n' % (header)
        open_symbol, close_symbol = '<', '>'

    libchrome_pattern = re.compile('#include %s(%s)/.*' %
                                   (open_symbol, LIBCHROME_DIRS))

    if line_to_add in lines:
        return

    _, end_include = get_include_range(lines)
    begin_libchrome_include, end_libchrome_include = get_libchrome_include_range(
        lines, libchrome_pattern)

    if begin_libchrome_include >= 0:
        lines[begin_libchrome_include:end_libchrome_include] = sorted(
            lines[begin_libchrome_include:end_libchrome_include] +
            [line_to_add])
    elif end_include >= 0:
        lines[end_include:end_include] = [line_to_add, '\n']
    else:
        lines = [line_to_add, '\n'] + lines

    with open(filename, 'w') as f:
        f.write(''.join(lines))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
