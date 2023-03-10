# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Presubmit script for dev-util repo

See http://dev.chromium.org/developers/how-tos/depottools/presubmit-scripts for
details on the presubmit API built into git cl.

Note that this file is compatible with `repo` workloads thanks to the
`git_cl_presubmit` hook. As a result, any checks made in this file work with
both git-cl and repo workflows. See:
https://chromium.googlesource.com/chromiumos/repohooks/+/HEAD/README.md#Hook-Overrides
"""

import subprocess


# Optional but recommended
PRESUBMIT_VERSION = "2.0.0"

# Mandatory: run under Python 3
USE_PYTHON3 = True

CTP_DIR = "src/chromiumos/ctp"


def RunProcess(cmd):  # pragma: no cover
    """Runs a process using the given command and returns the output.

    Args:
      cmd: The shell command string to be executed.

    Returns:
      The output of the process.

    Raises:
      subprocess.CalledProcessError: If the process return code is none zero.
    """
    process = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )

    return str(process.stdout, "utf-8")


# Unit tests CTP client codebase if a changed to the CTP files is merged.
# This would ideally be in `src/chromiumos/ctp`, but `repo upload` only runs
# against `PRESUBMIT.py` at the top level of a repo, so we need this logic here
def CheckCTPOnUpload(input_api, output_api):
    results = []

    file_filter = lambda x: CTP_DIR in x.LocalPath()
    ctp_files = input_api.AffectedFiles(file_filter=file_filter)

    if len(ctp_files) == 0:
        return results

    input_api.logging.info("Running go tests")

    try:
        output = RunProcess("./src/chromiumos/ctp/run_go_unittests.sh")
    except subprocess.CalledProcessError as e:
        # pull stdout/err from command into error for better end user message
        raise RuntimeError(e.output.decode("unicode-escape"))

    if output:
        results.append(output_api.PresubmitNotifyResult(output))

    return results
