// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dut

import (
	"context"
	"fmt"
	"io"
	"os/exec"
)

// unpackStateful unpacks the compressed stateful partition.
func unpackStateful(ctx context.Context, r io.Reader) error {
	cmd := exec.CommandContext(ctx,
		"tar",
		"--ignore-command-error",
		"--overwrite",
		"--selinux",
		"--directory", statefulDir,
		"-xzf",
		"-",
	)
	cmd.Stdin = r
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("tar unpack failed: %w: %s", err, out)
	}
	return nil
}
