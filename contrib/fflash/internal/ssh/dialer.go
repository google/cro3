// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ssh

import (
	"bufio"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path"
	"strings"

	"golang.org/x/crypto/ssh"
)

// SshOptions is the set of all supported ssh options.
type SshOptions struct {
	Port string
}

// Dialer is responsible for creating new ssh connections with a given set of ssh options.
type Dialer struct {
	sshOptions SshOptions
	keyChain   *KeyChain
}

// NewDialer creates a new ssh dialer which will create ssh clients and tunnels based on the provided options.
func NewDialer(sshOptions SshOptions) (*Dialer, error) {
	keyChain, err := NewKeyChain()
	if err != nil {
		return nil, err
	}

	return &Dialer{
		sshOptions: sshOptions,
		keyChain:   keyChain,
	}, nil
}

// DialWithSystemSSH connects to destination and return a Client.
// Affected by ssh_config(5).
//
// It uses the ssh command on the system, which understands user SSH configuration (~/.ssh/config)
// to make the initial connection. A tunnel: a UNIX domain socket is then set to forward traffic
// to port 22 on the destination system. Then the Client is created, by connecting
// to the UNIX domain socket. The benefit of doing so is to avoid the need of
// parsing ssh configuration, while still having a programmatic API, instead of
// having to deal with ssh child processes.
func (d *Dialer) DialWithSystemSSH(ctx context.Context, destination string) (*Client, error) {
	tunnel, err := d.newTunnel(ctx, destination)
	if err != nil {
		return nil, err
	}

	config := &ssh.ClientConfig{
		User: "root",
		Auth: []ssh.AuthMethod{
			d.keyChain.SSHAuthMethod(),
		},
		HostKeyCallback: ssh.InsecureIgnoreHostKey(),
	}
	sshClient, err := ssh.Dial("unix", tunnel.SSHServerSocket(), config)
	if err != nil {
		tunnel.Close()
		return nil, err
	}

	return &Client{
		tunnel: tunnel,
		Client: sshClient,
	}, nil
}

// DefaultCommand returns a SSH command with default flags set.
func (d *Dialer) DefaultCommand(ctx context.Context) *exec.Cmd {
	cmd := exec.CommandContext(ctx, "ssh",
		"-oBatchMode=yes",
		"-oUserKnownHostsFile=/dev/null",
		"-oStrictHostKeyChecking=no",
		"-oConnectTimeout=10",
		"-oServerAliveInterval=1",
		"-oUser=root",
	)
	cmd.Args = append(cmd.Args, d.keyChain.SSHCommandOptions()...)

	if d.sshOptions.Port != "" {
		cmd.Args = append(cmd.Args,
			"-p", d.sshOptions.Port,
		)
	}

	return cmd
}

// Closes the ssh dialer.
func (d *Dialer) Close() error {
	return d.keyChain.Delete()
}

// newTunnel creates a SSH Tunnel to host.
func (d *Dialer) newTunnel(ctx context.Context, host string) (*Tunnel, error) {
	tunnel := &Tunnel{}

	tempDir, err := os.MkdirTemp("", "ssh-tunnel-*")
	if err != nil {
		return nil, fmt.Errorf("cannot create temporary directory for ssh tunnel: %w", err)
	}
	if strings.Contains(tempDir, ":") {
		panic("temporary directory name contains ':'")
	}
	tunnel.tempDir = tempDir

	cmd := d.DefaultCommand(ctx)
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
