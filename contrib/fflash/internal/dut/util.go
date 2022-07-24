// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dut

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

func runCommand(ctx context.Context, name string, args ...string) (string, error) {
	cmd := exec.CommandContext(ctx, name, args...)
	output, err := cmd.Output()
	if err != nil {
		if err, ok := err.(*exec.ExitError); ok {
			return "", fmt.Errorf("%s failed: %w: %s", cmd, err, err.Stderr)
		}
		return "", fmt.Errorf("%s failed: %w", cmd, err)
	}
	return strings.TrimRight(string(output), "\n"), nil
}

func runCommandStderr(ctx context.Context, name string, args ...string) error {
	cmd := exec.CommandContext(ctx, name, args...)
	cmd.Stdout = os.Stderr
	cmd.Stderr = os.Stderr
	if err := cmd.Run(); err != nil {
		return fmt.Errorf("%s failed: %w", cmd, err)
	}
	return nil
}
