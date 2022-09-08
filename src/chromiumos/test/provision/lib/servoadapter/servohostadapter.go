// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.
package servoadapter

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
	"log"
	"strconv"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"
	"google.golang.org/grpc"
)

var ErrNotImplemented = errors.New("LocalAdapter: not implemented")

const CurlWithRetriesArgs = "-S -s -v -# -C - --retry 3 --retry-delay 60"

// ServoHostInterface is used to interface with a ServoHost
type ServoHostInterface interface {
	services.ServiceAdapterInterface

	// Returns value of a variable, requested with dut-control.
	GetVariable(ctx context.Context, varName string) (string, error)
	// Runs a single dut-control command with |args| as its arguments.
	RunDutControl(ctx context.Context, args []string) error
	// Runs an array of dut-control commands.
	RunAllDutControls(ctx context.Context, cmdFragments [][]string) error

	GetBoard(ctx context.Context) string
	GetModel(ctx context.Context) string
}

type ServoHostAdapter struct {
	execCmder ExecCmder
	port      int
	board     string
	// model aka variant is currently required.
	model string
}

// ServodServiceClient minus unused functionality.
type ExecCmder interface {
	// ExecCmd executes a system command that is provided through the command
	// parameter in the request. It allows the user to execute arbitrary commands
	// that can't be handled by calling servod (e.g. update firmware through
	// "futility", remote file copy through "scp").
	ExecCmd(ctx context.Context, in *api.ExecCmdRequest, opts ...grpc.CallOption) (*api.ExecCmdResponse, error)
}

// NewServoHostAdapterFromExecCmder adds extra functions to the ExecCmder.
func NewServoHostAdapterFromExecCmder(board, model string, port int, execCmder ExecCmder) ServoHostInterface {
	return &ServoHostAdapter{execCmder, port, board, model}
}

// RunCmd takes a command and argument and executes it remotely on the ServoHost
// by transforming the request to api.ExecCmdRequest, sending the request out,
// and transforming the response from api.ExecCmdResponse to (string, error).
// Returns the stdout as the string result and any execution error as the error.
func (s *ServoHostAdapter) RunCmd(ctx context.Context, cmd string, args []string) (string, error) {
	req := api.ExecCmdRequest{
		Command: fmt.Sprint(cmd, " ", strings.Join(args, " ")),
	}
	log.Println("[ServoHost] running command:", req.Command)
	resp, err := s.execCmder.ExecCmd(ctx, &req, grpc.EmptyCallOption{})
	if resp.GetExitInfo().GetStatus() != 0 || err != nil {
		annotatedErr := errors.Annotate(err, string(resp.GetStderr())).Err()
		annotatedErr = errors.Annotate(annotatedErr, "ExecCmdRequest failed on remote ServoHost").Err()
		return string(resp.GetStdout()), annotatedErr
	}
	return string(resp.GetStdout()), nil
}

func (s *ServoHostAdapter) Restart(ctx context.Context) error {
	return errors.New("attempted to restart the ServoHost")
}

// GetVariable reads value of varName from servo.
func (s *ServoHostAdapter) GetVariable(ctx context.Context, varName string) (string, error) {
	out, err := s.RunCmd(ctx, "dut-control", []string{"-p", strconv.Itoa(s.port), varName})
	if err != nil {
		return "", err
	}
	splitStr := strings.SplitN(out, varName+":", 2)
	if len(splitStr) > 1 {
		return strings.TrimRight(splitStr[1], "\r\n"), nil
	} else {
		return "", fmt.Errorf("failed to extract value \"%v\" from string \"%v\"", varName, out)
	}
}

// RunDutControl runs a dut-control command with provided arguments.
func (s *ServoHostAdapter) RunDutControl(ctx context.Context, args []string) error {
	cmdArgs := []string{"-p", strconv.Itoa(s.port)}
	cmdArgs = append(cmdArgs, args...)
	_, err := s.RunCmd(ctx, "dut-control", cmdArgs)
	return err
}

// RunAllCmd sequentially runs all cmdFragments as dut-control commands.
func (s *ServoHostAdapter) RunAllDutControls(ctx context.Context, cmdFragments [][]string) error {
	for i := 0; i < len(cmdFragments); i++ {
		if err := s.RunDutControl(ctx, cmdFragments[i]); err != nil {
			return err
		}
	}
	return nil
}

// PathExists determines if a path exists in a DUT
func (s ServoHostAdapter) PathExists(ctx context.Context, path string) (bool, error) {
	exists, err := s.RunCmd(ctx, "", []string{"[", "-e", path, "]", "&&", "echo", "-n", "1", "||", "echo", "-n", "0"})
	if err != nil {
		return false, fmt.Errorf("path exists: failed to check if %s exists, %s", path, err)
	}
	return exists == "1", nil
}

// PipeData uses the caching infrastructure to bring a file locally,
// allowing a user to pipe the result to any desired application.
func (s ServoHostAdapter) PipeData(ctx context.Context, sourceUrl string, pipeCommand string) error {
	return ErrNotImplemented
}

// CopyData caches a file for a DUT locally from a GS url.
func (s ServoHostAdapter) CopyData(ctx context.Context, sourceUrl string, destPath string) error {
	var cmd string
	var args []string
	if strings.HasPrefix(sourceUrl, "gs://") {
		cmd = "gsutil"
		args = []string{"cp", sourceUrl, destPath}
	} else {
		cmd = "curl"
		args = strings.Split(CurlWithRetriesArgs, " ")
		args = append(args, sourceUrl, "-o", destPath)
	}
	out, err := s.RunCmd(ctx, cmd, args)
	if err != nil {
		err = fmt.Errorf("downloading %v to %v failed: %w\n%v", sourceUrl, destPath, err, out)
	}
	return err
}

// DeleteDirectory is a thin wrapper around an rm command. Done here as it is
// expected to be reused often by many services.
func (s ServoHostAdapter) DeleteDirectory(ctx context.Context, dir string) error {
	if _, err := s.RunCmd(ctx, "rm", []string{"-rf", dir}); err != nil {
		return fmt.Errorf("could not delete directory, %w", err)
	}
	return nil
}

// Create directories is a thin wrapper around an mkdir command. Done here as it
// is expected to be reused often by many services.
func (s ServoHostAdapter) CreateDirectories(ctx context.Context, dirs []string) error {
	if _, err := s.RunCmd(ctx, "mkdir", append([]string{"-p"}, dirs...)); err != nil {
		return fmt.Errorf("could not create directory, %w", err)
	}
	return nil
}

func (s *ServoHostAdapter) GetBoard(ctx context.Context) string {
	return s.board
}
func (s *ServoHostAdapter) GetModel(ctx context.Context) string {
	return s.model
}
