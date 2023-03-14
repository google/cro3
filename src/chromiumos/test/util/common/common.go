// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package common

import (
	"context"
	"fmt"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
)

// RunCmd runs a command in a remote DUT via DutServiceClient.
func RunCmd(ctx context.Context, cmd string, args []string, dut api.DutServiceClient) (string, error) {
	log.Printf("<post-process> Run cmd: %s, %s\n", cmd, args)
	req := api.ExecCommandRequest{
		Command: cmd,
		Args:    args,
		Stdout:  api.Output_OUTPUT_PIPE,
		Stderr:  api.Output_OUTPUT_PIPE,
	}
	stream, err := dut.ExecCommand(ctx, &req)
	if err != nil {
		log.Printf("<cros-provision> Run cmd FAILED: %s\n", err)
		return "", fmt.Errorf("execution fail: %w", err)
	}
	// Expecting single stream result
	execCmdResponse, err := stream.Recv()
	if err != nil {
		return "", fmt.Errorf("execution single stream result: %w", err)
	}
	if execCmdResponse.ExitInfo.Status != 0 {
		err = fmt.Errorf("status:%v message:%v", execCmdResponse.ExitInfo.Status, execCmdResponse.ExitInfo.ErrorMessage)
	}
	if string(execCmdResponse.Stderr) != "" {
		log.Printf("<post-process> execution finished with stderr: %s\n", string(execCmdResponse.Stderr))
	}
	return string(execCmdResponse.Stdout), err
}
