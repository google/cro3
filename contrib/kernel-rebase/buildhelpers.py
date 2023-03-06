# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# pylint: disable=encoding-missing

"""Build helpers"""

import multiprocessing
from multiprocessing import Manager
import os

from common import executor_io
from githelpers import checkout
from githelpers import is_dirty
import rebase_config


def do_on_cros_sdk_impl(command, ret_by_arg=None):
    """Implementation of execution of a command in cros_sdk"""

    result = {"exit_code": None, "output": None, "error_line": None}
    os.system("echo '" + command + "' > " + executor_io + "/commands &")
    os.system("cat " + executor_io + "/output > output.log")
    try:
        with open(executor_io + "/last_exit") as last_exit:
            ec = last_exit.read()
        result["exit_code"] = int(ec[:-1])
    except:  # pylint: disable=bare-except
        print("failed to read a valid exit code from last_exit")
        return {}
    try:
        with open("output.log") as output:
            result["output"] = output.read()
        lines = result["output"].splitlines()
        for n in range(len(lines)):  # pylint: disable=C0200
            if "Error 1" in lines[n]:
                result["error_line"] = n + 1
                break
    except:  # pylint: disable=bare-except
        print("failed to read output.log")
    if ret_by_arg is not None:
        for k, v in result.items():
            ret_by_arg[k] = v
    return result


def do_on_cros_sdk(command, timeout_s=None):
    """Executes a command in cros_sdk and returns its result"""

    if timeout_s is not None:
        manager = Manager()
        result = {}
        shared_dict = manager.dict()
        p = multiprocessing.Process(
            target=do_on_cros_sdk_impl,
            args=(
                command,
                shared_dict,
            ),
        )
        p.start()
        p.join(timeout_s)
        if p.is_alive():
            print("execution timed out, is executor.sh running in cros_sdk?")
            p.terminate()
            p.join()
        else:
            for k, v in shared_dict.items():
                result[k] = v
        return result
    return do_on_cros_sdk_impl(command)


def verify_build(sha, board=rebase_config.verify_board):
    """Executes a build and returns its status"""

    assert not is_dirty(
        "kernel-upstream"
    ), "There's a local diff in kernel repo. Clean it to continue."
    if sha is not None:
        checkout("kernel-upstream", sha)
    return do_on_cros_sdk(
        "emerge-" + board + " --color n -B " + rebase_config.verify_package
    )
