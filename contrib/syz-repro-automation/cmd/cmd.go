// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package cmd

import (
	"bytes"
	"context"
	"fmt"
	"io"
	"log"
	"os"
	"os/exec"
	"time"
)

// RunCmd runs the command string cmdStr, if print is true redirects output to stdout.
// Returns the command output.
func RunCmd(print bool, cmdStr ...string) (string, error) {
	cmd := exec.Command(cmdStr[0], cmdStr[1:]...)
	var stdout bytes.Buffer
	var stderr bytes.Buffer

	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if print {
		cmd.Stdout = io.MultiWriter(&stdout, os.Stdout)
		cmd.Stderr = io.MultiWriter(&stderr, os.Stdout)
	}
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("%v: %v", err, stderr.String())
	}

	return stdout.String(), nil
}

// RunCmdLog runs the command string cmdStr with specified timeout, redirects output to outputLog.
func RunCmdLog(outputLog string, timeout time.Duration, cmdStr ...string) error {
	ctx, cancel := context.WithTimeout(context.Background(), timeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, cmdStr[0], cmdStr[1:]...)

	outputFile, err := os.Create(outputLog)
	if err != nil {
		return err
	}
	defer outputFile.Close()

	writer := io.Writer(outputFile)
	cmd.Stdout = writer
	cmd.Stderr = writer

	if err := cmd.Run(); err != nil {
		// Ignore errors due to context deadlines.
		if ctx.Err() != nil {
			log.Printf("Ctx Error: %v", ctx.Err())
			return nil
		}
		return fmt.Errorf("cmd error: %v", err)
	}

	return nil
}
