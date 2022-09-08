// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ssh

import (
	"bufio"
	"context"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"strings"
)

const tunnelSocketName = "tunnel-socket"

// Tunnel is a UNIX domain socket forwarded to a remote by the system's SSH command.
// Tunnel is used to allow x/crypto/ssh to connect to SSH servers with complex configs.
type Tunnel struct {
	cmd      *exec.Cmd
	cmdStdin io.WriteCloser
	tempDir  string
}

// DefaultCommand returns a SSH command with default flags set.
func DefaultCommand(ctx context.Context) *exec.Cmd {
	return exec.CommandContext(ctx, "ssh",
		"-oBatchMode=yes",
		"-oUserKnownHostsFile=/dev/null",
		"-oConnectTimeout=10",
		"-oServerAliveInterval=1",
	)
}

// NewTunnel creates a SSH Tunnel to host.
func NewTunnel(ctx context.Context, host string) (*Tunnel, error) {
	tunnel := &Tunnel{}

	tempDir, err := os.MkdirTemp("", "ssh-tunnel-*")
	if err != nil {
		return nil, fmt.Errorf("cannot create temporary directory for ssh tunnel: %w", err)
	}
	if strings.Contains(tempDir, ":") {
		panic("temporary directory name contains ':'")
	}
	tunnel.tempDir = tempDir

	cmd := DefaultCommand(ctx)
	cmd.Args = append(cmd.Args,
		fmt.Sprintf("-L%s:localhost:22", path.Join(tempDir, tunnelSocketName)),
		host,
		"echo", "ping", "&&", "read",
	)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, fmt.Errorf("cannot setup stdin pipe: %w", err)
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("cannot setup stdout pipe: %w", err)
	}
	cmd.Stderr = os.Stderr
	if err := cmd.Start(); err != nil {
		return nil, fmt.Errorf("cannot create ssh connection: %w", err)
	}
	tunnel.cmd = cmd
	tunnel.cmdStdin = stdin

	line, err := bufio.NewReader(stdout).ReadString('\n')
	if err != nil {
		tunnel.Close()
		return nil, err
	}
	if line != "ping\n" {
		tunnel.Close()
		return nil, fmt.Errorf("found unexpected ssh output %q", line)
	}

	return tunnel, nil
}

// Close the tunnel.
func (t *Tunnel) Close() error {
	if t.cmd != nil {
		t.cmdStdin.Close()
		t.cmd.Wait()
	}
	return os.RemoveAll(t.tempDir)
}

// SSHServerSocket returns the path of the UNIX domain socket that forwards to
// the remote host's TCP port 22.
func (t *Tunnel) SSHServerSocket() string {
	return filepath.Join(t.tempDir, tunnelSocketName)
}
