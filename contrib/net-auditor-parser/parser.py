# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Parse auditd logs.

Parse the connect() and send/sendto/sendmsg/sendmmsg() syscall usages per
process basis. Print the frequency historgrams in stdout.

Example:
    python3 parser.py data/sample.txt
"""


import sys


DELIM = "----"
TYPE_SYSCALL = "SYSCALL"
TYPE_SOCKADDR = "SOCKADDR"
TYPE = "type"
EVENTID = "event_id"
SYSCALL = "syscall"
SYSCALL_CONN = "connect"
SYSCALL_SEND = "sendto"
SYSCALL_SENDMSG = "sendmsg"
SYSCALL_SENDMMSG = "sendmmsg"
FAM = "fam"
LADDR = "laddr"
LPORT = "lport"
PID = "pid"
PPID = "ppid"
UID = "uid"
COMM = "comm"
EXE = "exe"

IGNORE_ADDR_LIST = ["127.0.0.1", "0.0.0.0", "::", "::1"]


def main(argv):
    """Parse the log file and show frequency histogram.

    Format of the output is: '<number> <process_name>', meaning that the
    <proces_name> invoked the syscall <number> of times. Showing 2 histograms
    for connect() and for send/sendto/sendmsg/sendmmsg() respectively.

    Args:
        argv: A single element list, specifying the log file path
              e.g. ["data/sample.txt"].
    """
    data = parse_file(argv[0])

    # Show histogram for connect syscall
    visualize_syscalls([SYSCALL_CONN], data)
    # Show joint histogram for send,sento,sendmsg syscalls
    visualize_syscalls([SYSCALL_SEND, SYSCALL_SENDMSG, SYSCALL_SENDMMSG], data)


def visualize_syscalls(syscalls, data):
    """Print frequency histogram of per-process usage of sys_connect().

    To focus on the information sent off the device, ignores:
        * sockets that DO NOT use the internet protocol
        * loopback interfaces

    Args:
        syscalls: A list of syscalls we are interested in. Log entries are
                  accounted if matched to any of the syscalls in this list.
        data: The list of log entries. TODO(zauri): add example
    """
    stats = {}
    for data_point in data:
        # Skip the logs which don't contain the syscall information.
        if COMM in data_point and FAM in data_point:
            sysc, comm, fam, addr = [
                data_point[SYSCALL],
                data_point[COMM],
                data_point[FAM],
                data_point.get(LADDR, None),
            ]

            # Skip irrelevant log entries
            if (
                sysc not in syscalls
                or fam not in ["inet", "inet6"]
                or addr in IGNORE_ADDR_LIST
            ):
                continue

            stats[comm] = stats.get(comm, 0) + 1
        else:
            continue

    print(f"\nShowing stats for syscall={syscalls}:")
    for item in sorted(stats, key=stats.get, reverse=True):
        print(stats[item], "\t", item)


def parse_file(file_name):
    """Parse log file and return as a list of dictionary items.

    Args:
        file_name: path the log file.

    Returns:
        A list containing per-event information. The list elements are
        dictionaries, containing even-related data, like eventid, syscall, etc.
    """
    events = None
    with open(file_name, "r") as file:
        events = file.read().split(DELIM)
        events = list(filter(len, events))

    data = []
    for event in events:
        data.append(parse_event(event))

    return data


def parse_event(event):
    """Parse single event information into a data point.

    Multiple log entries are logged for each event. Logs of the other events
    are separated with '----' delimiter in a log file.
    This function takes all the log entries of a single event, parses out the
    required fields into a dictionary and returns it.

    Args:
        event: String containing all the logs of a single event.

    Returns:
        A dictionary with the relevant event information.
    """
    data_point = {}

    # Parse relevant fields.
    parse_eventid(event, data_point)
    parse_syscall_bits(event, data_point)
    parse_sockaddr_bits(event, data_point)

    return data_point


def parse_type(event, log_type):
    """Return the log entry with the desired log type.

    Args:
        event: String of all the log entries associated with a single event.
        log_type: Type of the log entry we're searcing for e.g. 'SYSCALL'.

    Returns:
        The first log entry of the given type (should be EXACTLY one).
        Returns empty string if the type is not found.
    """
    log_entries = event.split("\n")
    log_entries = list(filter(len, log_entries))
    log_entries = [e.rstrip() for e in log_entries]

    for entry in log_entries:
        cur_type = entry.split()[0].replace("type=", "")
        if cur_type == log_type:
            return entry

    return ""


def parse_eventid(event, data_point):
    """Parse EVENTID field into the data_point."""
    log_entry = event.split()[2].rstrip()

    eventid = log_entry.split(")")[0]
    eventid = eventid[eventid.rfind(":") + 1 :]

    data_point[EVENTID] = int(eventid)


def parse_syscall_bits(event, data_point):
    """Parse the type=SYSCALL-related fields into the data point."""
    sys_entry = parse_type(event, TYPE_SYSCALL)
    if sys_entry == "":
        return

    syscall, success, ppid, pid, auid, uid, gid, comm, exe, subj = [
        " syscall=",
        " success=",
        " ppid=",
        " pid=",
        " auid=",
        " uid=",
        " gid=",
        " comm=",
        " exe=",
        " subj=",
    ]
    data_point[SYSCALL] = sys_entry[
        sys_entry.find(syscall) + len(syscall) : sys_entry.find(success)
    ]
    data_point[PPID] = int(
        sys_entry[sys_entry.find(ppid) + len(ppid) : sys_entry.find(pid)]
    )
    data_point[PID] = int(
        sys_entry[sys_entry.find(pid) + len(pid) : sys_entry.find(auid)]
    )
    data_point[UID] = sys_entry[
        sys_entry.find(uid) + len(uid) : sys_entry.find(gid)
    ]
    data_point[COMM] = sys_entry[
        sys_entry.find(comm) + len(comm) : sys_entry.find(exe)
    ]
    data_point[EXE] = sys_entry[
        sys_entry.find(exe) + len(exe) : sys_entry.find(subj)
    ]


def parse_sockaddr_bits(event, data_point):
    """Parse the type=SOCKADDR-related bits into the data point."""
    sockaddr_entry = parse_type(event, TYPE_SOCKADDR)
    if sockaddr_entry == "":
        return

    fam, laddr, lport = [
        " fam=",
        " laddr=",
        " lport=",
    ]
    data_point[FAM] = sockaddr_entry[
        sockaddr_entry.find(fam) + len(fam) : sockaddr_entry.find(laddr)
    ]
    if data_point[FAM] == "inet" or data_point[FAM] == "inet6":
        data_point[LADDR] = sockaddr_entry[
            sockaddr_entry.find(laddr) + len(laddr) : sockaddr_entry.find(lport)
        ]
        data_point[LPORT] = int(
            sockaddr_entry[
                sockaddr_entry.find(lport)
                + len(lport) : sockaddr_entry.find(
                    " ", sockaddr_entry.find(lport) + 1
                )
            ]
        )
    else:
        # TODO(zauri): do we need non-inet[6] packets?
        pass


if __name__ == "__main__":
    main(sys.argv[1:])
