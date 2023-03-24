// Copyright 2023 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"regexp"
	"strings"

	"chromiumos/test/provision/v2/android-provision/service"
)

var reVersionCode = regexp.MustCompile(`^versionCode=(\d+).+`)

func getOSBuildId(ctx context.Context, dut *service.DUTConnection) (string, error) {
	args := []string{"-s", dut.SerialNumber, "shell", "getprop", "ro.build.id"}
	return dut.AssociatedHost.RunCmd(ctx, "adb", args)
}

func getOSIncrementalVersion(ctx context.Context, dut *service.DUTConnection) (string, error) {
	args := []string{"-s", dut.SerialNumber, "shell", "getprop", "ro.build.version.incremental"}
	return dut.AssociatedHost.RunCmd(ctx, "adb", args)
}

func getAndroidPackageVersionCode(ctx context.Context, dut *service.DUTConnection, packageName string) (string, error) {
	args := []string{"-s", dut.SerialNumber, "shell", "dumpsys", "package", packageName, "|", "grep", "versionCode", "|", "sort", "-r", "|", "head", "-n", "1"}
	out, err := dut.AssociatedHost.RunCmd(ctx, "adb", args)
	if err != nil {
		return "", err
	}
	return reVersionCode.ReplaceAllString(strings.TrimSpace(out), "$1"), nil
}
