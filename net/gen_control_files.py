# Copyright 2022 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Loop over carriers to generate cellular control files

Since cellular control files need to be repeated per carrier, generate
them. Also, spilt cellular tests into multiple control files so that
stable tests are run immediately after reboot.
"""

import argparse
import os


prefix = """# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

# Do not edit manually. Generated using ~/chromiumos/src/platform/dev/net/gen_control_files.py

AUTHOR = 'Chromium OS team'
NAME = 'tast.{primary_suite}-{carrier}-{tag}'
METADATA = {{
    "contacts": ["chromeos-cellular-team@google.com"],
    "bug_component": "b:167157", # ChromeOS > Platform > Connectivity > Cellular
    }}
TIME = 'MEDIUM'
TEST_TYPE = 'Server'
ATTRIBUTES = '{suites}'
MAX_RESULT_SIZE_KB = 1024 * 1024
PY_VERSION = 3
DEPENDENCIES = "carrier:{carrier}"

DOC = \'\'\'

See https://chromium.googlesource.com/chromiumos/platform/tast/ for
more information.

See http://go/tast-failures for information about investigating failures.
\'\'\'

import json
import tempfile
import yaml

def run(machine):
    host = hosts.create_host(machine)
    with tempfile.NamedTemporaryFile(suffix='.yaml', mode='w+') as temp_file:
        host_info = host.host_info_store.get()
        yaml.safe_dump({{'autotest_host_info_labels':
                        json.dumps(host_info.labels)}},
                        stream=temp_file)
        temp_file.flush()
"""

suffix = """
parallel_simple(run, machines)
"""

"""
Writes a control file at out_dir/control.suite-carrier-tag. The argument l_tests should specify the tests that need to be run in the control file. If l_suite contains more than one element, the l_suite[0] is used to name the control file.
"""


def write_control_file(l_out_dir, l_suite, l_carrier, l_tag, l_tests):
    primary_suite = l_suite[0]  # used to name the file and autotest
    suites = ""
    for i, s in enumerate(l_suite):
        if i == 0:
            suites = "suite:" + s
        else:
            suites = suites + ", suite:" + s

    with open(
        os.path.join(l_out_dir, f"control.{primary_suite}-{l_carrier}-{l_tag}"),
        "w",
    ) as control_file:
        control_file.write(
            prefix.format(
                primary_suite=primary_suite,
                carrier=l_carrier,
                tag=l_tag,
                suites=suites,
            )
            + l_tests
            + suffix
        )


single_test_template = """
        host.reboot()
        job.run_test('tast',
                    host=host,
                    clear_tpm = False,
                    test_exprs={test_exprs},
                    ignore_test_failures=True, max_run_sec=10800,
                    command_args=args,
                    varsfiles=[temp_file.name]
                    )
"""


parser = argparse.ArgumentParser()
parser.add_argument(
    "-o", "--out_dir", help="Output directory for control files"
)
args = parser.parse_args()
out_dir = (
    args.out_dir
    if args.out_dir
    else os.path.join(
        os.path.expanduser("~"),
        "chromiumos/src/third_party/autotest/files/server/site_tests/tast/",
    )
)

for carrier in [
    "verizon",
    "tmobile",
    "att",
    "amarisoft",
    "vodafone",
    "rakuten",
    "ee",
    "kddi",
    "docomo",
    "softbank",
]:

    dut_check_suites = ["cellular_ota", "cellular_repair"]
    if carrier in ["verizon", "tmobile", "att"]:
        dut_check_suites.append(
            "cellular-cq"
        )  # other carriers are sparsely deployed in the lab, thus CQ may fail to find DUTs

    tests = single_test_template.format(test_exprs="['cellular.IsModemUp']")
    write_control_file(out_dir, dut_check_suites, carrier, "is_modem_up", tests)

    tests = single_test_template.format(
        test_exprs=f"['cellular.Identifiers.{carrier}','cellular.IsConnected.{carrier}','cellular.Smoke.{carrier}', 'cellular.SmokeIPConnectivity.{carrier}']"
    )
    write_control_file(out_dir, dut_check_suites, carrier, "dut_check", tests)

    tests = single_test_template.format(
        test_exprs=f"['cellular.Autoconnect.{carrier}','cellular.ShillEnableDisable.{carrier}']"
    )
    write_control_file(
        out_dir,
        dut_check_suites,
        carrier,
        "autoconnect_enable",
        tests,
    )

    tests = single_test_template.format(
        test_exprs="['cellular.HostCellularNetworkConnectivity']"
    )
    write_control_file(
        out_dir, ["cellular_ota_flaky"], carrier, "for_stabilization", tests
    )

    tests = single_test_template.format(
        test_exprs="['cellular.ShillCellularEnableAndConnect','cellular.HostCellularStressEnableDisable','cellular.ModemmanagerEnableAndConnect','cellular.ShillCellularSafetyDance']"
    )
    write_control_file(
        out_dir, ["cellular_ota_flaky"], carrier, "stress", tests
    )

    exclude_sms = "" if carrier in ["tmobile", "att"] else ' && !"cellular_sms"'
    tests = single_test_template.format(
        test_exprs='[\'("group:cellular" && "cellular_sim_active" && "cellular_unstable" && !"cellular_run_isolated" && !"cellular_e2e"'
        + exclude_sms
        + ")']"
    )
    write_control_file(
        out_dir,
        ["cellular_ota_flaky", "cellular_repair"],
        carrier,
        "platform",
        tests,
    )

    tests = single_test_template.format(
        test_exprs='[\'("group:cellular" && "cellular_sim_active" && !"cellular_unstable" && !"cellular_run_isolated" && !"cellular_e2e"'
        + exclude_sms
        + ")']"
    )
    write_control_file(
        out_dir, ["cellular_ota", "cellular_repair"], carrier, "platform", tests
    )

    tests = single_test_template.format(
        test_exprs="['cellular.*SuspendResume*']"
    )
    write_control_file(
        out_dir,
        ["cellular_ota_flaky", "cellular_repair"],
        carrier,
        "suspend_resume",
        tests,
    )

    tests = single_test_template.format(
        test_exprs='[\'("group:cellular" && "cellular_sim_active" && "cellular_unstable" && "cellular_e2e")\']'
    )
    write_control_file(out_dir, ["cellular_ota_flaky"], carrier, "e2e", tests)

    tests = single_test_template.format(
        test_exprs='[\'("group:cellular" && "cellular_sim_active" && !"cellular_unstable" && "cellular_e2e")\']'
    )
    write_control_file(out_dir, ["cellular_ota"], carrier, "e2e", tests)
    tests = single_test_template.format(
        test_exprs='[\'("group:cellular_crosbolt" && "cellular_crosbolt_perf_nightly")\']'
    )
    write_control_file(
        out_dir, ["cellular_ota_perf_flaky"], carrier, "perf", tests
    )

    # limit carrier independent cq tests to tmobile to save lab time.
    if carrier == "tmobile":
        tests = single_test_template.format(
            test_exprs='[\'("group:cellular" && "cellular_sim_active" && !"cellular_run_isolated" && "cellular_cq")\']'
        )
        write_control_file(out_dir, ["cellular-cq"], carrier, "cq", tests)
