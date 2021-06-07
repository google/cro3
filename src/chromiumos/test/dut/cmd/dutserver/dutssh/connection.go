// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package dutssh

import (
	"io"

	"golang.org/x/crypto/ssh"
)

// This file only exists because go cannot mock structs and the ssh client
// library does not provide interfaces for testing.
type ClientInterface interface {
	Close() error
	NewSession() (SessionInterface, error)
}

type SSHClient struct {
	*ssh.Client
}

func (c *SSHClient) Close() error {
	return c.Client.Close()
}

func (c *SSHClient) NewSession() (SessionInterface, error) {
	session, err := c.Client.NewSession()
	if err != nil {
		return nil, err
	}
	return &SSHSession{Session: session}, nil
}

type SessionInterface interface {
	Close() error
	SetStdout(writer io.Writer)
	SetStderr(writer io.Writer)
	Run(cmd string) error
}

type SSHSession struct {
	*ssh.Session
}

func (s *SSHSession) Close() error {
	return s.Session.Close()
}
func (s *SSHSession) SetStdout(writer io.Writer) {
	s.Session.Stdout = writer
}

func (s *SSHSession) SetStderr(writer io.Writer) {
	s.Session.Stderr = writer
}

func (s *SSHSession) Run(cmd string) error {
	return s.Session.Run(cmd)
}
