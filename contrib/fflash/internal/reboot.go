// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package internal

import (
	"context"
	"fmt"
	"log"
	"time"

	"chromium.googlesource.com/chromiumos/platform/dev-util.git/contrib/fflash/internal/ssh"
)

const BootIdFile = "/proc/sys/kernel/random/boot_id"

// GetBootId returns the unique boot ID of c's remote host.
func GetBootId(ctx context.Context, c *ssh.Client) (string, error) {
	return c.RunSimpleOutput("cat " + BootIdFile)
}

// GetRebootingBootId attempts to connect to host using the system SSH command.
// Then returns the unique boot ID of the host.
func GetRebootingBootId(ctx context.Context, host string) (string, error) {
	ctx, cancel := context.WithTimeout(ctx, 12*time.Second)
	defer cancel()

	cmd := ssh.DefaultCommand(ctx)
	cmd.Args = append(cmd.Args, host, "cat", BootIdFile)
	out, err := cmd.Output()
	return string(out), err
}

// WaitReboot waits the ssh host to reboot
func WaitReboot(ctx context.Context, host string, oldBootID string) error {
	ctx, cancel := context.WithTimeout(ctx, 10*time.Minute)
	defer cancel()

	for ctx.Err() == nil {
		ticker := time.NewTicker(time.Second)
		defer ticker.Stop()
		for range ticker.C {
			BootID, err := GetRebootingBootId(ctx, host)
			if err != nil {
				continue
			}
			if BootID != oldBootID {
				return nil
			}
		}
	}
	return fmt.Errorf("failed to out wait for DUT reboot: %s", ctx.Err())
}

// Reboot the device connected with client and wait for the host to be online
func Reboot(ctx context.Context, client *ssh.Client, host string) error {
	bootID, err := GetBootId(ctx, client)
	if err != nil {
		return fmt.Errorf("cannot get current boot ID of DUT %s", bootID)
	}

	log.Println("rebooting host:", host)
	if _, err := client.RunSimpleOutput("sh -c 'nohup sleep 1 && reboot &'"); err != nil {
		return fmt.Errorf("failed to schedule reboot")
	}
	client.Close()

	return WaitReboot(ctx, host, bootID)
}