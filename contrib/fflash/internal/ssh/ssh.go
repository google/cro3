// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ssh

import (
	"bytes"
	"errors"
	"fmt"

	"golang.org/x/crypto/ssh"
)

// Client is a custom SSH client with extra utility methods.
type Client struct {
	tunnel *Tunnel
	*ssh.Client
}

// Close the client.
func (c *Client) Close() error {
	c.Client.Close()
	return c.tunnel.Close()
}

// NewSession creates a new Session. A session is used to run a command.
func (c *Client) NewSession() (*Session, error) {
	s, err := c.Client.NewSession()
	return &Session{Session: s}, err
}

// RunSimpleOutput runs cmd on the remote system.
// Stdout is returned as a string.
// On error, the stderr is contained in the returned error.
func (c *Client) RunSimpleOutput(cmd string) (string, error) {
	s, err := c.NewSession()
	if err != nil {
		return "", err
	}
	defer s.Close()
	return s.SimpleOutput(cmd)
}

type Session struct {
	*ssh.Session
}

// SimpleOutput runs cmd on the remote system.
// Stdout is returned as a string.
// On error, the stderr is contained in the returned error.
func (s *Session) SimpleOutput(cmd string) (string, error) {
	if s.Stdout != nil {
		return "", errors.New("exec: Stdout already set")
	}
	if s.Stderr != nil {
		return "", errors.New("exec: Stderr already set")
	}
	var stdout bytes.Buffer
	var stderr bytes.Buffer
	s.Stdout = &stdout
	s.Stderr = &stderr
	err := s.Run(cmd)
	if err != nil {
		return stdout.String(), fmt.Errorf("ssh command %q failed: %w: %s", cmd, err, stderr.String())
	}
	return stdout.String(), nil
}
