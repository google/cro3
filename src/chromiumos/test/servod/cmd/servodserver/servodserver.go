// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements servod_service.proto (see proto for details)
package servodserver

import (
	"bytes"
	"context"
	"errors"
	"infra/libs/sshpool"
	"io"
	"log"
	"strings"

	"chromiumos/lro"
	"chromiumos/test/servod/cmd/commandexecutor"
	"chromiumos/test/servod/cmd/model"
	"chromiumos/test/servod/cmd/servod"

	"chromiumos/test/servod/cmd/ssh"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	crypto_ssh "golang.org/x/crypto/ssh"
)

// ServodService implementation of servod_service.proto
type ServodService struct {
	manager         *lro.Manager
	logger          *log.Logger
	commandexecutor commandexecutor.CommandExecutorInterface
	sshPool         *sshpool.Pool
	servodPool      *servod.Pool
}

// NewServodService creates a new servod service.
func NewServodService(ctx context.Context, logger *log.Logger, commandexecutor commandexecutor.CommandExecutorInterface) (*ServodService, func(), error) {
	servodService := &ServodService{
		manager:         lro.New(),
		logger:          logger,
		commandexecutor: commandexecutor,
		sshPool:         sshpool.New(ssh.SSHConfig()),
		servodPool:      servod.NewPool(),
	}

	destructor := func() {
		servodService.manager.Close()
	}

	return servodService, destructor, nil
}

// StartServod runs a servod Docker container and starts the servod daemon
// inside the container if servod is containerized. Otherwise, it simply
// starts the servod daemon.
func (s *ServodService) StartServod(ctx context.Context, req *api.StartServodRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.StartServodRequest: ", *req)
	op := s.manager.NewOperation()

	a := model.CliArgs{
		ServoHostPath:             req.ServoHostPath,
		ServodDockerContainerName: req.ServodDockerContainerName,
		ServodDockerImagePath:     req.ServodDockerImagePath,
		ServodPort:                req.ServodPort,
		Board:                     req.Board,
		Model:                     req.Model,
		SerialName:                req.SerialName,
		Debug:                     req.Debug,
		RecoveryMode:              req.RecoveryMode,
		Config:                    req.Config,
		AllowDualV4:               req.AllowDualV4,
	}

	_, bErr, err := s.RunCli(model.CliStartServod, a, nil, false)
	if err != nil {
		s.logger.Println("Failed to run CLI: ", err)
		s.manager.SetResult(op.Name, &api.StartServodResponse{
			Result: &api.StartServodResponse_Failure_{
				Failure: &api.StartServodResponse_Failure{
					ErrorMessage: getErrorMessage(bErr, err),
				},
			},
		})
	} else {
		s.manager.SetResult(op.Name, &api.StartServodResponse{
			Result: &api.StartServodResponse_Success_{},
		})
	}

	return op, err
}

// StopServod stops the servod daemon inside the container and stops the
// servod Docker container if servod is containerized. Otherwise, it simply
// stops the servod daemon.
func (s *ServodService) StopServod(ctx context.Context, req *api.StopServodRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.StopServodRequest: ", *req)
	op := s.manager.NewOperation()

	a := model.CliArgs{
		ServoHostPath:             req.ServoHostPath,
		ServodDockerContainerName: req.ServodDockerContainerName,
		ServodPort:                req.ServodPort,
	}

	_, bErr, err := s.RunCli(model.CliStopServod, a, nil, false)
	if err != nil {
		s.logger.Println("Failed to run CLI: ", err)
		s.manager.SetResult(op.Name, &api.StopServodResponse{
			Result: &api.StopServodResponse_Failure_{
				Failure: &api.StopServodResponse_Failure{
					ErrorMessage: getErrorMessage(bErr, err),
				},
			},
		})
	} else {
		s.manager.SetResult(op.Name, &api.StopServodResponse{
			Result: &api.StopServodResponse_Success_{},
		})
	}

	return op, err
}

// ExecCmd executes a system command that is provided through the command
// parameter in the request. It allows the user to execute arbitrary commands
// that can't be handled by calling servod (e.g. update firmware through
// "futility", remote file copy through "scp").
// It executes the command inside the servod Docker container if the
// servod_docker_container_name parameter is provided in the request.
// Otherwise, it executes the command directly inside the host that the servo
// is physically connected to.
func (s *ServodService) ExecCmd(ctx context.Context, req *api.ExecCmdRequest) (*api.ExecCmdResponse, error) {
	s.logger.Println("Received api.ExecCmdRequest: ", *req)

	a := model.CliArgs{
		ServoHostPath:             req.ServoHostPath,
		ServodDockerContainerName: req.ServodDockerContainerName,
		Command:                   req.Command,
	}

	var stdin io.Reader = nil
	if len(req.Stdin) > 0 {
		stdin = bytes.NewReader(req.Stdin)
	}

	bOut, bErr, err := s.RunCli(model.CliExecCmd, a, stdin, false)
	if err != nil {
		s.logger.Println("Failed to run CLI: ", err)
	}
	return &api.ExecCmdResponse{
		ExitInfo: getExitInfo(err),
		Stdout:   bOut.Bytes(),
		Stderr:   bErr.Bytes(),
	}, err
}

// CallServod runs a servod command through an XML-RPC call.
// It runs the command inside the servod Docker container if the
// servod_docker_container_name parameter is provided in the request.
// Otherwise, it runs the command directly inside the host that the servo
// is physically connected to.
// Allowed methods: doc, get, set, and hwinit.
func (s *ServodService) CallServod(ctx context.Context, req *api.CallServodRequest) (*api.CallServodResponse, error) {
	s.logger.Println("Received api.CallServodRequest: ", *req)

	sd, err := s.servodPool.Get(
		req.ServoHostPath,
		req.ServodPort,
		// This method must return non-nil value for servod.Get to work so return a dummy array.
		func() ([]string, error) {
			return []string{}, nil
		})
	if err != nil {
		return &api.CallServodResponse{
			Result: &api.CallServodResponse_Failure_{
				Failure: &api.CallServodResponse_Failure{
					ErrorMessage: err.Error(),
				},
			},
		}, err
	}

	val, err := sd.Call(ctx, s.sshPool, strings.ToLower(req.Method.String()), req.Args)
	if err != nil {
		return &api.CallServodResponse{
			Result: &api.CallServodResponse_Failure_{
				Failure: &api.CallServodResponse_Failure{
					ErrorMessage: err.Error(),
				},
			},
		}, err
	}

	return &api.CallServodResponse{
		Result: &api.CallServodResponse_Success_{
			Success: &api.CallServodResponse_Success{
				Result: val,
			},
		},
	}, nil
}

// getErrorMessage returns either Stderr output or error message
func getErrorMessage(bErr bytes.Buffer, err error) string {
	errorMessage := bErr.String()
	if errorMessage == "" {
		errorMessage = err.Error()
	}
	return errorMessage
}

// getExitInfo extracts exit info from Session Run's error
func getExitInfo(runError error) *api.ExecCmdResponse_ExitInfo {
	// If no error, command succeeded
	if runError == nil {
		return createCommandSucceededExitInfo()
	}

	// If ExitError, command ran but did not succeed
	var ee *crypto_ssh.ExitError
	if errors.As(runError, &ee) {
		return createCommandFailedExitInfo(ee)
	}

	// Otherwise we assume command failed to start
	return createFailedToStartExitInfo(runError)
}

func createFailedToStartExitInfo(err error) *api.ExecCmdResponse_ExitInfo {
	return &api.ExecCmdResponse_ExitInfo{
		Status:       42, // Contract dictates arbitrary response, thus 42 is as good as any number
		Signaled:     false,
		Started:      false,
		ErrorMessage: err.Error(),
	}
}

func createCommandSucceededExitInfo() *api.ExecCmdResponse_ExitInfo {
	return &api.ExecCmdResponse_ExitInfo{
		Status:       0,
		Signaled:     false,
		Started:      true,
		ErrorMessage: "",
	}
}

func createCommandFailedExitInfo(err *crypto_ssh.ExitError) *api.ExecCmdResponse_ExitInfo {
	return &api.ExecCmdResponse_ExitInfo{
		Status:       int32(err.ExitStatus()),
		Signaled:     true,
		Started:      true,
		ErrorMessage: "",
	}
}
