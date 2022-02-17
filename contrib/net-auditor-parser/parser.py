# // Copyright 2022 The Chromium OS Authors. All rights reserved.
# // Use of this source code is governed by a BSD-style license that can be
# // found in the LICENSE file.

"""Parse auditd logs.

Parse the connect() syscall usage per process basis.
Print the frequency historgram in stdout.

Example:
    python3 parser.py data/sample_data.txt
"""


import sys


DELIM = '----'
SYSCALL = 'SYSCALL'
SOCKADDR = 'SOCKADDR'
EVENTID = 'event_id'
TYPE = 'type'
FAM = 'fam'
LADDR = 'laddr'
LPORT = 'lport'
PID = 'pid'
PPID = 'ppid'
UID = 'uid'
COMM = 'comm'
EXE = 'exe'

IGNORE_ADDR_LIST = ['127.0.0.1', '0.0.0.0', '::', '::1']


def main(argv):
    """Parse the log file and show frequency histogram.

    Format of the output is: '<number> <process_name>', meaning that the
    <proces_name> invoked the connect() syscall <number> of times.

    Args:
        argv: A single element list, specifying the log file path
              e.g. ["data/sample_output.txt"].
    """
    data = parse_file(argv[0])
    visualize(data)


def visualize(data):
    """Print frequency histogram of per-process usage of sys_connect().

    We want to observe what information is sent off of devices.
    Consequently, ignoring:
    * sockets that DO NOT use internet protocol
    * loopback interfaces
    """
    stats = {}
    for data_point in data:
        # Skip the logs which don't contain the syscall information.
        if COMM in data_point and FAM in data_point:
            comm, fam, addr = [
                data_point[COMM],
                data_point[FAM],
                data_point.get(LADDR, None),
            ]

            # Ignore non-internet protocols
            if fam not in ['inet', 'inet6']:
                continue
            # Ignore loopback addresses.
            if addr in IGNORE_ADDR_LIST:
                continue

            stats[comm] = stats.get(comm, 0) + 1
        else:
            continue

    for item in sorted(stats, key=stats.get, reverse=True):
        print(stats[item], '\t', item)


def parse_file(file_name):
    """Parse log file and return as a list of dictionary items.

    Args:
        file_name: path the log file.

    Returns:
        A list containing per-event information.
    """
    events = None
    with open(file_name, 'r') as file:
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
        log_type: Type of the log entry we're searcing for e.g. 'SYSCALL.

    Returns:
        The first log entry of the given type (should be EXACTLY one).
        Returns empty string if the type is not found.
    """
    log_entries = event.split('\n')
    log_entries = list(filter(len, log_entries))
    log_entries = [e.rstrip() for e in log_entries]

    for entry in log_entries:
        cur_type = entry.split()[0].replace('type=', '')
        if cur_type == log_type:
            return entry

    return ''


def parse_eventid(event, data_point):
    """Populate EVENTID field of the data_point."""
    log_entry = event.split()[2].rstrip()

    eventid = log_entry.split(')')[0]
    eventid = eventid[eventid.rfind(':')+1:]

    data_point[EVENTID] = int(eventid)


def parse_syscall_bits(event, data_point):
    """Populate the SYSCALL-related fields into a data point."""
    sys_entry = parse_type(event, SYSCALL)
    if sys_entry == '':
        return

    ppid, pid, auid, uid, gid, comm, exe, subj = [
        ' ppid=',
        ' pid=',
        ' auid=',
        ' uid=',
        ' gid=',
        ' comm=',
        ' exe=',
        ' subj=',
        ]
    data_point[PPID] = int(sys_entry[sys_entry.find(ppid)+len(ppid)
                                     : sys_entry.find(pid)])
    data_point[PID] = int(sys_entry[sys_entry.find(pid)+len(pid)
                                    : sys_entry.find(auid)])
    data_point[UID] = sys_entry[sys_entry.find(uid)+len(uid)
                                : sys_entry.find(gid)]
    data_point[COMM] = sys_entry[sys_entry.find(comm)+len(comm)
                                 : sys_entry.find(exe)]
    data_point[EXE] = sys_entry[sys_entry.find(exe)+len(exe)
                                : sys_entry.find(subj)]


def parse_sockaddr_bits(event, data_point):
    """Populate the SOCKADDR-related bits into a data point."""
    sockaddr_entry = parse_type(event, SOCKADDR)
    if sockaddr_entry == '':
        return

    fam, laddr, lport = [
        ' fam=',
        ' laddr=',
        ' lport=',
        ]
    data_point[FAM] = sockaddr_entry[sockaddr_entry.find(fam)+len(fam)
                                     : sockaddr_entry.find(laddr)]
    if data_point[FAM] == 'inet' or data_point[FAM] == 'inet6':
        data_point[LADDR] = sockaddr_entry[sockaddr_entry.find(laddr)
                                           + len(laddr)
                                           : sockaddr_entry.find(lport)]
        data_point[LPORT] = int(sockaddr_entry[
            sockaddr_entry.find(lport) + len(lport)
            : sockaddr_entry.find(' ', sockaddr_entry.find(lport)+1)])
    else:
        # TODO(zauri): do we need non-inet[6] packets?
        pass


if __name__ == '__main__':
    main(sys.argv[1:])
