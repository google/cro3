// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ssh

import (
	"io"
	"os"
	"os/exec"
	"path/filepath"
)

const tunnelSocketName = "tunnel-socket"

// Tunnel is a UNIX domain socket forwarded to a remote by the system's SSH command.
// Tunnel is used to allow x/crypto/ssh to connect to SSH servers with complex configs.
type Tunnel struct {
	cmd      *exec.Cmd
	cmdStdin io.WriteCloser
	tempDir  string
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
