// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commandexecutor

import (
	"bytes"
	"chromiumos/test/dut/cmd/cros-dut/dutssh"
	"io"
	"log"
	"os"
	"os/exec"

	"golang.org/x/crypto/ssh"
)

// ServodCommandExecutor acts as a receiver to implement CommandExecutorInterface
// by running given commands either locally or on a remote host through os/exec
// and SSH run commands.
type ServodCommandExecutor struct {
	logger *log.Logger
}

func NewServodCommandExecutor(logger *log.Logger) ServodCommandExecutor {
	return ServodCommandExecutor{
		logger: logger,
	}
}

// Run executes a given command either on a remote host specified by addr
// or locally when addr is empty or "localhost".
func (s ServodCommandExecutor) Run(addr string, command string, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
	var bOut bytes.Buffer
	var bErr bytes.Buffer
	var err error

	localMode := addr == "" || addr == "localhost"
	if localMode {
		cmd := exec.Command("bash", "-c", command)

		// Route the incoming Stdin to system Stdin
		if stdin != nil {
			cmd.Stdin = stdin
		}

		// Route session Stdout/Stderr to system Stdout/Stderr
		if routeToStd {
			cmd.Stdout = os.Stdout
			cmd.Stderr = os.Stderr
		} else {
			cmd.Stdout = &bOut
			cmd.Stderr = &bErr
		}

		// Run the command
		err = cmd.Run()
	} else {
		config := dutssh.GetSSHConfig()
		var client *ssh.Client
		client, err = ssh.Dial("tcp", addr, config)
		if err != nil {
			s.logger.Fatal("Failed to dial: ", err)
		}
		defer client.Close()

		var session *ssh.Session
		session, err = client.NewSession()
		if err != nil {
			s.logger.Fatal("Failed to create session: ", err)
		}
		defer session.Close()

		// Route the incoming Stdin to system Stdin
		if stdin != nil {
			session.Stdin = stdin
		}

		// Route session Stdout/Stderr to system Stdout/Stderr
		if routeToStd {
			session.Stdout = os.Stdout
			session.Stderr = os.Stderr
		} else {
			session.Stdout = &bOut
			session.Stderr = &bErr
		}

		// Run the command
		err = session.Run(command)
	}

	// Log session stdout if it's not routed to system stdout
	if bOut.Len() > 0 {
		s.logger.Print(bOut.String())
	}
	// Log session stderr if it's not routed to system stderr
	if bErr.Len() > 0 {
		s.logger.Print(bErr.String())
	}

	return bOut, bErr, err
}
