# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Common code for client and server"""


def print_field(msg, name):
    """Prints field name and value"""

    try:
        if msg.HasField(name):
            val = getattr(msg, name)
            print(f"{name} -> {val}")
    except ValueError:
        pass


def print_msg(msg):
    """Prints name and value of each field in the message"""

    print(type(msg))
    elems = dir(msg)
    for elem in elems:
        if callable(elem):
            print("Callable: " + elem)
            continue
        if elem.startswith("__"):
            continue
        if elem.startswith("_"):
            continue
        if elem[0].isupper():
            continue
        print_field(msg, elem)
    print("")
