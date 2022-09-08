// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ssh

import (
	"context"
	"fmt"
	"log"
	"os/exec"
	"strings"
	"syscall"

	clog "chromiumos/platform/dev/contrib/labtunnel/log"
)

const sshCmd = "ssh"
const tunnelKeepaliveCmd = "sleep 8h"

type Runner struct {
	sshOpts   []string
	nextCmdId int
}

func NewRunner(sshOpts []string) *Runner {
	return &Runner{
		sshOpts:   sshOpts,
		nextCmdId: 1,
	}
}

func (r *Runner) buildCmd(ctx context.Context, sshOpts []string, flags []string, posArgs []string) (*exec.Cmd, *log.Logger, error) {

	// Process arguments.
	args := make([]string, 0)
	if sshOpts != nil {
		for _, opt := range sshOpts {
			opt = strings.TrimPrefix(opt, "-o ")
			optParts := strings.Split(opt, "=")
			if len(optParts) != 2 {
				return nil, nil, fmt.Errorf("invalid ssh option %q", opt)
			}
			optKey := optParts[0]
			optValue := optParts[1]
			optValue = strings.TrimPrefix(optValue, "\"")
			optValue = strings.TrimSuffix(optValue, "\"")
			opt = fmt.Sprintf("%s=%q", optKey, optValue)
			args = append(args, []string{"-o", opt}...)
		}
	}
	if flags != nil {
		for _, flagStr := range flags {
			flagParts := strings.Split(flagStr, " ")
			flag := strings.TrimPrefix(strings.TrimPrefix(flagParts[0], "-"), "-")
			if len(flag) == 1 {
				flag = "-" + flag
			} else {
				flag = "--" + flag
			}
			args = append(args, flag)
			if len(flagParts) > 1 {
				// Add the rest of the flag parts back as a single argument.
				args = append(args, strings.Join(flagParts[1:], " "))
			}
		}
	}
	if posArgs != nil {
		args = append(args, posArgs...)
	}

	// Build cmd and ensure ssh and its forked processes are grouped.
	cmd := exec.CommandContext(ctx, sshCmd, args...)
	cmd.SysProcAttr = &syscall.SysProcAttr{
		Setpgid:   true,
		Pdeathsig: syscall.SIGKILL,
	}

	// Capture command output to log with a unique prefix.
	logPrefix := fmt.Sprintf("SSH[%d]: ", r.nextCmdId)
	r.nextCmdId++
	cmdLogger := clog.NewLogger(logPrefix)
	logWriter := clog.NewWriter(cmdLogger)
	cmd.Stdout = logWriter
	cmd.Stderr = logWriter

	return cmd, cmdLogger, nil
}

func (r *Runner) Run(ctx context.Context, flags []string, posArgs []string) error {
	cmd, cmdLogger, err := r.buildCmd(ctx, r.sshOpts, flags, posArgs)
	if err != nil {
		return err
	}
	cmdLogger.Printf("RUN: %s", cmd.String())

	// Wait for run to complete or context is cancelled.
	runChan := make(chan error)
	var runErr error
	go func() {
		runChan <- cmd.Run()
	}()
	select {
	case <-ctx.Done():
		runErr = ctx.Err()
		break
	case runErr = <-runChan:
		break
	}

	// Silently kill this ssh process group.
	if cmd.Process != nil {
		_ = syscall.Kill(-cmd.Process.Pid, syscall.SIGKILL)
	}
	return runErr
}

func (r *Runner) TunnelLocalPortToRemotePort(ctx context.Context, localPort int, remoteHost string, remotePort int, sshHost string) error {
	if remoteHost == "" {
		remoteHost = "localhost"
	}
	flags := []string{
		fmt.Sprintf("-L %d:%s:%d", localPort, remoteHost, remotePort),
	}
	posArgs := []string{
		sshHost,
		tunnelKeepaliveCmd,
	}
	return r.Run(ctx, flags, posArgs)
}
