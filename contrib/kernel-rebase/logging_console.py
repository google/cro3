# Copyright 2021 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# import checking doesn't always work
# pylint: disable=import-error

"""Console that logs output of each command to a file in log/"""

import atexit
import code
from datetime import datetime
import os
import readline
import rlcompleter
import sys

import sh


# Python's default history path
histfile = os.path.expanduser("~/.python_history")


def save_history():
    """appends command history to the history file"""
    readline.set_history_length(10000)
    readline.write_history_file(histfile)


class Logger:
    """Splits stdout into stdout and a file"""

    def __init__(self):
        sh.mkdir("-p", "log/triage/")
        ts = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        filename = ts + ".log"
        if os.path.exists("log/latest"):
            sh.rm("log/latest")
        sh.ln("-s", filename, "log/latest")
        self.terminal = sys.stdout
        self.log = open("log/" + filename, "w")

    def write(self, message):
        """Forwards write() call to self.terminal and self.log"""

        self.terminal.write(message)

        # prepend lines written to the log file with timestamps
        ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        lines_ts = []
        for line in message.strip().splitlines():
            lines_ts.append(f"[{ts}] {line}\n")
        message_ts = "".join(lines_ts)

        self.log.write(message_ts)

    def flush(self):
        """Forwards flush() call to self.terminal and self.log"""

        self.terminal.flush()
        self.log.flush()


class LoggingConsole(code.InteractiveConsole):
    """code.InteractiveConsole that logs console output"""

    def __init__(self, local=None):
        code.InteractiveConsole.__init__(self, local)
        self.logger = Logger()
        try:
            readline.read_history_file(histfile)
            atexit.register(save_history)
        except FileNotFoundError:
            pass
        readline.set_completer(rlcompleter.Completer(local).complete)
        readline.parse_and_bind("tab: complete")

    def push(self, line):
        """temporarily subsistute a Logger() instance before forwarding the push() call

        This is necessary because the InteractiveConsole will refuse to support history
        if sys.stdout isn't the default value.
        """

        sys.stdout = self.logger
        super().push(line)
        sys.stdout = self.logger.terminal
