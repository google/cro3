// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"context"
	"strings"
	"time"

	"go.chromium.org/luci/common/errors"

	"chromiumos/test/provision/v2/android-provision/service"
)

// rebootToBootloader reboots DUT into bootloader mode.
func rebootToBootloader(ctx context.Context, dut *service.DUTConnection, cmd string) error {
	args := []string{"-s", dut.SerialNumber, "reboot", "bootloader"}
	if _, err := dut.AssociatedHost.RunCmd(ctx, cmd, args); err != nil {
		return err
	}
	// Device may take some time to boot into bootloader.
	maxWaitTime := 10 * time.Second
	return waitForBootloaderMode(ctx, dut, maxWaitTime)
}

// waitForBootloaderMode waits until the device gets into the bootloader mode.
func waitForBootloaderMode(ctx context.Context, dut *service.DUTConnection, waitTimeout time.Duration) error {
	waitInRetry := 1 * time.Second
	retryCount := int(waitTimeout / waitInRetry)
	args := []string{"devices", "|", "grep", dut.SerialNumber}
	for {
		stdOut, err := dut.AssociatedHost.RunCmd(ctx, "fastboot", args)
		if err != nil {
			return err
		}
		if strings.HasPrefix(stdOut, dut.SerialNumber) {
			return nil
		}
		retryCount -= 1
		if retryCount <= 0 {
			return errors.Reason("failed to wait for dut bootloader mode").Err()
		}
		time.Sleep(waitInRetry)
	}
}
