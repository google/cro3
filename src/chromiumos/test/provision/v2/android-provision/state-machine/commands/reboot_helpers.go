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

// rebootToSystem reboots DUT to booting system image.
func rebootToSystem(ctx context.Context, dut *service.DUTConnection, cmd string) error {
	args := []string{"-s", dut.SerialNumber, "reboot"}
	if _, err := dut.AssociatedHost.RunCmd(ctx, cmd, args); err != nil {
		return err
	}
	// Device takes some time to boot.
	maxWaitTime := 120 * time.Second
	return waitForDevice(ctx, dut, maxWaitTime)
}

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

// waitForBootloaderMode waits until DUT reboots into bootloader mode.
func waitForBootloaderMode(ctx context.Context, dut *service.DUTConnection, waitTimeout time.Duration) error {
	waitInRetry := 1 * time.Second
	retryCount := int(waitTimeout / waitInRetry)
	args := []string{"devices", "|", "grep", "-sw", dut.SerialNumber, "|", "awk", "'{print $2}'"}
	for {
		ds, err := dut.AssociatedHost.RunCmd(ctx, "fastboot", args)
		if err != nil {
			return err
		}
		if state := strings.TrimSuffix(ds, "\n"); state == "fastboot" {
			return nil
		}
		retryCount -= 1
		if retryCount <= 0 {
			return errors.Reason("failed to wait for dut bootloader mode").Err()
		}
		time.Sleep(waitInRetry)
	}
}

// waitForDevice waits until DUT reboots.
func waitForDevice(ctx context.Context, dut *service.DUTConnection, waitTimeout time.Duration) error {
	waitInRetry := 5 * time.Second
	retryCount := int(waitTimeout / waitInRetry)
	stateCount := 3
	// Ensure the consistent device state at least <stateCount> times in a row.
	successCount, failureCount := 0, 0
	args := []string{"devices", "|", "grep", "-sw", dut.SerialNumber, "|", "awk", "'{print $2}'"}
	for {
		// Read device state
		if ds, err := dut.AssociatedHost.RunCmd(ctx, "adb", args); err != nil {
			successCount = 0
			failureCount += 1
		} else {
			if state := strings.TrimSuffix(ds, "\n"); state == "device" {
				successCount += 1
				failureCount = 0
				if successCount >= stateCount {
					break
				}
			} else {
				successCount = 0
				if state == "unauthorized" {
					failureCount += 1
					// If device is in unauthorized state for more than 90 seconds, return error.
					// The device either broken or public key is missing.
					if failureCount >= 16 {
						return errors.Reason("dut state is '%s'", ds).Err()
					}
				}
			}
		}
		retryCount -= 1
		if retryCount <= 0 {
			break
		}
		time.Sleep(waitInRetry)
	}
	if successCount < stateCount {
		return errors.Reason("failed to wait for dut normal mode").Err()
	}
	return nil
}
