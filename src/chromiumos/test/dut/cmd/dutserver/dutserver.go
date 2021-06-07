// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements dut_service.proto (see proto for details)
package main

import (
	"bytes"
	"context"
	"errors"
	"log"
	"net"

	"go.chromium.org/chromiumos/config/go/test/api"
	"golang.org/x/crypto/ssh"
	"google.golang.org/grpc"

	"chromiumos/test/dut/cmd/dutserver/dutssh"
)

// DutServiceServer implementation of dut_service.proto
type DutServiceServer struct {
	logger     *log.Logger
	connection dutssh.ClientInterface
}

// newDutServiceServer creates a new dut service server to listen to rpc requests.
func newDutServiceServer(l net.Listener, logger *log.Logger, conn dutssh.ClientInterface) *grpc.Server {
	s := &DutServiceServer{
		logger:     logger,
		connection: conn,
	}

	server := grpc.NewServer()
	api.RegisterDutServiceServer(server, s)
	logger.Println("dutservice listen to request at ", l.Addr().String())
	return server
}

// ExecCommand remotely executes a command on the DUT.
func (s *DutServiceServer) ExecCommand(req *api.ExecCommandRequest, stream api.DutService_ExecCommandServer) error {
	s.logger.Println("Received api.ExecCommandRequest: ", *req)
	resp := s.runCmd(req.Command)
	return stream.Send(resp)
}

// FetchCrashes remotely fetches crashes from the DUT.
func (s *DutServiceServer) FetchCrashes(req *api.FetchCrashesRequest, stream api.DutService_FetchCrashesServer) error {
	s.logger.Println("Received api.FetchCrashesRequest: ", *req)
	return stream.Send(&api.FetchCrashesResponse{})
}

// GetConnection resolves the dut address name to ip address and ssh into it
func GetConnection(ctx context.Context, dutAddress string, wiringAddress string) (*ssh.Client, error) {
	addr, err := dutssh.GetSSHAddr(ctx, dutAddress, wiringAddress)
	if err != nil {
		return nil, err
	}

	return ssh.Dial("tcp", addr, dutssh.GetSSHConfig())
}

// runCmd run remote command returning return value, stdout, stderr, and error if any
func (s *DutServiceServer) runCmd(cmd string) *api.ExecCommandResponse {
	session, err := s.connection.NewSession()
	if err != nil {
		return &api.ExecCommandResponse{
			ExitInfo: createFailedToStartExitInfo(err),
		}
	}
	defer session.Close()

	var stdOut bytes.Buffer
	var stdErr bytes.Buffer
	session.SetStdout(&stdOut)
	session.SetStderr(&stdErr)
	err = session.Run(cmd)

	return &api.ExecCommandResponse{
		Stdout:   stdOut.Bytes(),
		Stderr:   stdErr.Bytes(),
		ExitInfo: getExitInfo(err),
	}
}

// getExitInfo extracts exit info from Session Run's error
func getExitInfo(runError error) *api.ExecCommandResponse_ExitInfo {
	// If no error, command succeeded
	if runError == nil {
		return createCommandSucceededExitInfo()
	}

	// If ExitError, command ran but did not succeed
	var ee *ssh.ExitError
	if errors.As(runError, &ee) {
		return createCommandFailedExitInfo(ee)
	}

	// Otherwise we assume command failed to start
	return createFailedToStartExitInfo(runError)
}

func createFailedToStartExitInfo(err error) *api.ExecCommandResponse_ExitInfo {
	return &api.ExecCommandResponse_ExitInfo{
		Status:       42, // Contract dictates arbitrary response, thus 42 is as good as any number
		Signaled:     false,
		Started:      false,
		ErrorMessage: err.Error(),
	}
}

func createCommandSucceededExitInfo() *api.ExecCommandResponse_ExitInfo {
	return &api.ExecCommandResponse_ExitInfo{
		Status:       0,
		Signaled:     false,
		Started:      true,
		ErrorMessage: "",
	}
}

func createCommandFailedExitInfo(err *ssh.ExitError) *api.ExecCommandResponse_ExitInfo {
	return &api.ExecCommandResponse_ExitInfo{
		Status:       int32(err.ExitStatus()),
		Signaled:     true,
		Started:      true,
		ErrorMessage: "",
	}
}
