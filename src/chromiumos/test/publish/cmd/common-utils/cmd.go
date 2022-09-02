// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common_utils

import (
	"bytes"
	"context"
	"log"
	"os/exec"
	"time"
)

// RunWithTimeout supports running any cli command with timeout
func RunWithTimeout(ctx context.Context, cmd *exec.Cmd, timeout time.Duration, block bool) (stdout string, stderr string, err error) {
	var se, so bytes.Buffer
	cmd.Stderr = &se
	cmd.Stdout = &so
	defer func() {
		stdout = so.String()
		stderr = se.String()
	}()

	log.Printf("Run cmd: %q", cmd)
	if block {
		err = cmd.Run()
	} else {
		err = cmd.Start()
	}

	if err != nil {
		log.Printf("error found with cmd: %q: %s", cmd, err)
	}
	return
}
