// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ssh

import (
	"bytes"
	"context"
	"fmt"
	"log"
	"time"

	"golang.org/x/crypto/ssh"

	"infra/libs/sshpool"
)

const (
	defaultSSHUser = "root"

	// Some tasks such as running badblocks for USB-Drive audit can
	// take quite long (2-3 hours). We need to set timeout limit to
	// accommodate such tasks.
	defaultSSHTimeout = time.Hour * 3
	DefaultPort       = 22
)

// getSSHConfig provides default config for SSH.
func SSHConfig() *ssh.ClientConfig {
	return &ssh.ClientConfig{
		User:            defaultSSHUser,
		HostKeyCallback: ssh.InsecureIgnoreHostKey(),
		Timeout:         defaultSSHTimeout,
		Auth:            []ssh.AuthMethod{ssh.PublicKeys(SSHSigner)},
	}
}

// RunResult represents result of executed command.
type RunResult struct {
	// Command executed on the resource.
	Command string
	// Exit code return.
	// Eg: 0 - everything is good
	// 	   1 - executed stop with error code `1`
	//     15 - timeout of execution
	ExitCode int
	// Standard output
	Stdout string
	// Standard error output
	Stderr string
}

// Run executes command on the target address by SSH.
func Run(ctx context.Context, pool *sshpool.Pool, addr string, cmd string) (result *RunResult) {
	result = &RunResult{
		Command:  cmd,
		ExitCode: -1,
	}
	if pool == nil {
		result.Stderr = "run SSH: pool is not initialized"
		return
	} else if addr == "" {
		result.Stderr = "run SSH: addr is empty"
		return
	} else if cmd == "" {
		result.Stderr = fmt.Sprintf("run SSH %q: cmd is empty", addr)
		return
	}
	sc, err := pool.GetContext(ctx, addr)
	if err != nil {
		result.Stderr = fmt.Sprintf("run SSH %q: fail to get client from pool; %s", addr, err)
		return
	}
	defer func() { pool.Put(addr, sc) }()
	result = internalRunSSH(cmd, sc)
	log.Println(ctx, "run SSH %q: Cmd: %q; ExitCode: %d; Stdout: %q;  Stderr: %q", addr, result.Command, result.ExitCode, result.Stdout, result.Stderr)
	return
}

func internalRunSSH(cmd string, client *ssh.Client) (result *RunResult) {
	result = &RunResult{
		Command:  cmd,
		ExitCode: -1,
	}
	session, err := client.NewSession()
	if err != nil {
		result.Stderr = fmt.Sprintf("internal run SSH: %s", err)
		return
	}
	defer func() { session.Close() }()
	var stdOut, stdErr bytes.Buffer
	session.Stdout = &stdOut
	session.Stderr = &stdErr

	err = session.Run(cmd)

	result.Stdout = stdOut.String()
	result.Stderr = stdErr.String()
	if err == nil {
		result.ExitCode = 0
	} else if exitErr, ok := err.(*ssh.ExitError); ok {
		result.ExitCode = exitErr.ExitStatus()
	} else if _, ok := err.(*ssh.ExitMissingError); ok {
		result.ExitCode = -2
		result.Stderr = err.Error()
	} else {
		// Set error 1 as not expected exit.
		result.ExitCode = -3
		result.Stderr = err.Error()
	}
	return
}
