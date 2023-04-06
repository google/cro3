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

func getBoard(ctx context.Context, dut *service.DUTConnection) (string, error) {
	args := []string{"-s", dut.SerialNumber, "shell", "getprop", "ro.product.board"}
	board, err := dut.AssociatedHost.RunCmd(ctx, "adb", args)
	if err != nil {
		return "", err
	}
	return strings.TrimSuffix(board, "\n"), nil
}

func getOSBuildId(ctx context.Context, dut *service.DUTConnection) (string, error) {
	args := []string{"-s", dut.SerialNumber, "shell", "getprop", "ro.build.id"}
	buildId, err := dut.AssociatedHost.RunCmd(ctx, "adb", args)
	if err != nil {
		return "", err
	}
	return strings.TrimSuffix(buildId, "\n"), nil
}

func getOSVersion(ctx context.Context, dut *service.DUTConnection) (string, error) {
	args := []string{"-s", dut.SerialNumber, "shell", "getprop", "ro.build.version.release"}
	releaseVersion, err := dut.AssociatedHost.RunCmd(ctx, "adb", args)
	if err != nil {
		return "", err
	}
	return strings.TrimSuffix(releaseVersion, "\n"), nil
}

func getOSIncrementalVersion(ctx context.Context, dut *service.DUTConnection) (string, error) {
	args := []string{"-s", dut.SerialNumber, "shell", "getprop", "ro.build.version.incremental"}
	osVersion, err := dut.AssociatedHost.RunCmd(ctx, "adb", args)
	if err != nil {
		return "", err
	}
	return strings.TrimSuffix(osVersion, "\n"), nil
}

func getAndroidPackageVersionCode(ctx context.Context, dut *service.DUTConnection, packageName string) (string, error) {
	args := []string{"-s", dut.SerialNumber, "shell", "dumpsys", "package", packageName, "|", "grep", "versionCode", "|", "sort", "-r", "|", "head", "-n", "1"}
	out, err := dut.AssociatedHost.RunCmd(ctx, "adb", args)
	if err != nil {
		return "", err
	}
	return reVersionCode.ReplaceAllString(strings.TrimSpace(out), "$1"), nil
}
