# Copyright 2023 The ChromiumOS Authors
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

load("@io_bazel_rules_go//go:def.bzl", "go_binary")

def dut_agent_binary(name, goarch):
    if not name.endswith("-" + goarch):
        fail("The name of dut-agent for goarch={0} must end with -{0}".format(goarch))
    go_binary(
        name = name,
        embed = [":dut-agent_lib"],
        gc_linkopts = [
            "-w",
            "-s",
        ],
        goarch = goarch,
        goos = "linux",
        pure = "on",
        static = "on",
        visibility = ["//visibility:public"],
    )
