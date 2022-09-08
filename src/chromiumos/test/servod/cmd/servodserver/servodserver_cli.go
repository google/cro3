// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package servodserver

import (
	"bytes"
	"chromiumos/test/servod/cmd/model"
	"fmt"
	"io"
	"strings"

	"go.chromium.org/luci/common/errors"
)

// RunCli runs servod service as execution by CLI.
func (s *ServodService) RunCli(cs model.CliSubcommand, a model.CliArgs, stdin io.Reader, routeToStd bool) (bytes.Buffer, bytes.Buffer, error) {
	s.logger.Println("Start running the servod service CLI.")

	var bOut bytes.Buffer
	var bErr bytes.Buffer
	var err error

	command := ""
	switch cs {
	case model.CliStartServod:
		command, err = s.getStartServodCommand(a)
	case model.CliStopServod:
		command = s.getStopServodCommand(a)
	case model.CliExecCmd:
		command = s.getExecCmdCommand(a)
	case model.CliCallServod:
		command = s.getCallServodCommand(a)
	}

	if command != "" {
		s.logger.Printf("Execute command: %s", command)
		bOut, bErr, err = s.commandexecutor.Run(a.ServoHostPath, command, stdin, routeToStd)
		if err != nil {
			return bOut, bErr, err
		}
		s.logger.Println("Finished running the servod service CLI successfully!")
	}

	return bOut, bErr, err
}

// getStartServodCommand returns either a "docker run" command when
// ServodDockerImagePath is specified or a "start servod" command
// when ServodDockerImagePath is empty.
func (s *ServodService) getStartServodCommand(a model.CliArgs) (string, error) {
	if a.Board == "" {
		return "", errors.Reason("Board not specified").Err()
	}
	if a.Model == "" {
		return "", errors.Reason("Model not specified").Err()
	}
	if a.SerialName == "" {
		return "", errors.Reason("SerialName not specified").Err()
	}

	command := ""
	if a.ServodDockerImagePath != "" {
		if a.ServodDockerContainerName == "" {
			return "", errors.Reason("ServodDockerContainerName not specified").Err()
		}
		command = fmt.Sprintf("docker run -d --network host --name %s %s --cap-add=NET_ADMIN --volume=/dev:/dev --privileged %s /start_servod.sh",
			a.ServodDockerContainerName, getStartServodEnv(a, "--env "), a.ServodDockerImagePath)
	} else {
		command = fmt.Sprintf("start servod %s", getStartServodEnv(a, ""))
	}
	return command, nil
}

// getStartServodEnv returns environment variables as a string.
// envPrefix is applied to each environment variable (e.g. Docker --env parameter).
func getStartServodEnv(a model.CliArgs, envPrefix string) string {
	env := fmt.Sprintf("%sPORT=%d", envPrefix, a.ServodPort)
	env = fmt.Sprintf("%s %sBOARD=%s", env, envPrefix, a.Board)
	env = fmt.Sprintf("%s %sMODEL=%s", env, envPrefix, a.Model)
	env = fmt.Sprintf("%s %sSERIAL=%s", env, envPrefix, a.SerialName)
	if a.AllowDualV4 != "" {
		env = fmt.Sprintf("%s %sDUAL_V4=%s", env, envPrefix, a.AllowDualV4)
	}
	if a.Config != "" {
		env = fmt.Sprintf("%s %sCONFIG=%s", env, envPrefix, a.Config)
	}
	if a.Debug != "" {
		env = fmt.Sprintf("%s %sDEBUG=%s", env, envPrefix, a.Debug)
	}
	if a.RecoveryMode != "" {
		env = fmt.Sprintf("%s %sREC_MODE=%s", env, envPrefix, a.RecoveryMode)
	}
	return env
}

// getStopServodCommand returns either a "docker stop" command when
// ServodDockerContainerName is specified or a "stop servod" command
// when ServodDockerContainerName is empty.
func (s *ServodService) getStopServodCommand(a model.CliArgs) string {
	command := ""
	if a.ServodDockerContainerName != "" {
		command = fmt.Sprintf("docker exec -d %s /stop_servod.sh && docker stop %s",
			a.ServodDockerContainerName, a.ServodDockerContainerName)
	} else {
		command = fmt.Sprintf("stop servod PORT=%d", a.ServodPort)
	}
	return command
}

// getExecCmdCommand returns either a "docker exec" command when
// ServodDockerContainerName is specified or the command provided
// when ServodDockerContainerName is empty.
func (s *ServodService) getExecCmdCommand(a model.CliArgs) string {
	if a.ServodDockerContainerName != "" {
		return fmt.Sprintf("docker exec -d %s '%s'",
			a.ServodDockerContainerName, a.Command)
	} else {
		return a.Command
	}
}

// getCallServodCommand returns either a "docker exec" command when
// ServodDockerContainerName is specified or a "dut-control" command
// when ServodDockerContainerName is empty.
func (s *ServodService) getCallServodCommand(a model.CliArgs) string {
	command := ""
	// Generate a "dut-control" command based on the method and args provided.
	switch strings.ToLower(a.Method) {
	case "doc":
		command = fmt.Sprintf("dut-control -p %d -i %s", a.ServodPort, a.Args)
	case "get", "set":
		command = fmt.Sprintf("dut-control -p %d %s", a.ServodPort, a.Args)
	}

	if a.ServodDockerContainerName != "" {
		return fmt.Sprintf("docker exec -d %s '%s'",
			a.ServodDockerContainerName, command)
	} else {
		return command
	}
}
