// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Service interfaces bases
package services

import (
	"context"
	"fmt"
	"time"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"
)

// ServiceAdapters are used to interface with a DUT
// All methods here are proxies to cros-dut (with some additions for simplicity)
type ServiceAdapterInterface interface {
	// RunCmd takes a command and argument and executes it remotely in the DUT,
	// returning the stdout as the string result and any execution error as the error.
	RunCmd(ctx context.Context, cmd string, args []string) (string, error)
	// Restart restarts a DUT (allowing cros-dut to reconnect for connection caching).
	Restart(ctx context.Context) error
	// PathExists is a simple wrapper for RunCmd for the sake of simplicity. If
	// the path exists True is returned, else False. An error implies a
	// a communication failure.
	PathExists(ctx context.Context, path string) (bool, error)
	// PipeData uses the caching infrastructure to bring an image into the lab.
	// Contrary to CopyData, the data here is pipeable to whatever is fed into
	// pipeCommand, rather than directly placed locally.
	PipeData(ctx context.Context, sourceUrl string, pipeCommand string) error
	// CopyData uses the caching infrastructure to copy a remote image to
	// the local path specified by destPath.
	CopyData(ctx context.Context, sourceUrl string, destPath string) error
	// DeleteDirectory is a simple wrapper for RunCmd for the sake of simplicity.
	DeleteDirectory(ctx context.Context, dir string) error
	// CreateDirectory is a simple wrapper for RunCmd for the sake of simplicity.
	// All directories specified in the array will be created.
	// As this uses "-p" option, subdirs are created regardless of whether parents
	// exist or not.
	CreateDirectories(ctx context.Context, dirs []string) error
}

type ServiceAdapter struct {
	dutName    string
	dutClient  api.DutServiceClient
	wiringConn *grpc.ClientConn
	noReboot   bool
}

func NewServiceAdapter(dutName string, dutClient api.DutServiceClient, wiringConn *grpc.ClientConn, noReboot bool) ServiceAdapter {
	return ServiceAdapter{
		dutName:    dutName,
		dutClient:  dutClient,
		wiringConn: wiringConn,
		noReboot:   noReboot,
	}
}

// RunCmd runs a command in a remote DUT
func (s ServiceAdapter) RunCmd(ctx context.Context, cmd string, args []string) (string, error) {
	fmt.Printf("Run cmd: %s, %s\n", cmd, args)
	req := api.ExecCommandRequest{
		Command: cmd,
		Args:    args,
		Stdout:  api.Output_OUTPUT_PIPE,
		Stderr:  api.Output_OUTPUT_PIPE,
	}
	stream, err := s.dutClient.ExecCommand(ctx, &req)
	if err != nil {
		return "", fmt.Errorf("execution fail: %w", err)
	}
	// Expecting single stream result
	feature, err := stream.Recv()
	if err != nil {
		return "", fmt.Errorf("execution single stream result: %w", err)
	}
	fmt.Printf("Run cmd response: %s\n", feature)
	if string(feature.Stderr) != "" {
		fmt.Printf("execution finished with stderr: %s\n", string(feature.Stderr))
	}
	return string(feature.Stdout), nil
}

// Restart restarts a DUT
func (s ServiceAdapter) Restart(ctx context.Context) error {
	if s.noReboot {
		return nil
	}

	req := api.RestartRequest{
		Args: []string{},
	}

	ctx, cancel := context.WithTimeout(ctx, 300*time.Second)
	defer cancel()

	op, err := s.dutClient.Restart(ctx, &req)
	if err != nil {
		return err
	}

	for !op.Done {
		time.Sleep(1 * time.Second)
	}

	switch x := op.Result.(type) {
	case *longrunning.Operation_Error:
		return fmt.Errorf(x.Error.Message)
	case *longrunning.Operation_Response:
		return nil
	}

	return nil

}

// PathExists determines if a path exists in a DUT
func (s ServiceAdapter) PathExists(ctx context.Context, path string) (bool, error) {
	exists, err := s.RunCmd(ctx, "", []string{"[", "-e", path, "]", "&&", "echo", "-n", "1", "||", "echo", "-n", "0"})
	if err != nil {
		return false, fmt.Errorf("path exists: failed to check if %s exists, %s", path, err)
	}
	return exists == "1", nil
}

// PipeData uses the caching infrastructure to bring a file locally,
// allowing a user to pipe the result to any desired application.
func (s ServiceAdapter) PipeData(ctx context.Context, sourceUrl string, pipeCommand string) error {
	fmt.Printf("Piping %s with command %s\n", sourceUrl, pipeCommand)

	req := api.CacheRequest{
		Source: &api.CacheRequest_GsFile{
			GsFile: &api.CacheRequest_GSFile{
				SourcePath: sourceUrl,
			},
		},
		Destination: &api.CacheRequest_Pipe_{
			Pipe: &api.CacheRequest_Pipe{
				Commands: pipeCommand,
			},
		},
	}

	op, err := s.dutClient.Cache(ctx, &req)
	if err != nil {
		return fmt.Errorf("execution failure: %v", err)
	}

	for !op.Done {
		time.Sleep(1 * time.Second)
	}

	switch x := op.Result.(type) {
	case *longrunning.Operation_Error:
		return fmt.Errorf(x.Error.Message)
	case *longrunning.Operation_Response:
		return nil
	}

	return nil

}

// CopyData caches a file for a DUT locally from a GS url.
func (s ServiceAdapter) CopyData(ctx context.Context, sourceUrl string, destPath string) error {
	fmt.Printf("Copy data from: %s, to: %s\n", sourceUrl, destPath)

	req := api.CacheRequest{
		Source: &api.CacheRequest_GsFile{
			GsFile: &api.CacheRequest_GSFile{
				SourcePath: sourceUrl,
			},
		},
		Destination: &api.CacheRequest_File{
			File: &api.CacheRequest_LocalFile{
				Path: destPath,
			},
		},
	}

	op, err := s.dutClient.Cache(ctx, &req)
	if err != nil {
		return fmt.Errorf("execution failure: %v", err)
	}

	for !op.Done {
		time.Sleep(1 * time.Second)
	}

	switch x := op.Result.(type) {
	case *longrunning.Operation_Error:
		return fmt.Errorf(x.Error.Message)
	case *longrunning.Operation_Response:
		return nil
	}

	return nil
}

// DeleteDirectory is a thin wrapper around an rm command. Done here as it is
// expected to be reused often by many services.
func (s ServiceAdapter) DeleteDirectory(ctx context.Context, dir string) error {
	if _, err := s.RunCmd(ctx, "rm", []string{"-rf", dir}); err != nil {
		return fmt.Errorf("could not delete directory, %w", err)
	}
	return nil
}

// Create directories is a thin wrapper around an mkdir command. Done here as it
// is expected to be reused often by many services.
func (s ServiceAdapter) CreateDirectories(ctx context.Context, dirs []string) error {
	if _, err := s.RunCmd(ctx, "mkdir", append([]string{"-p"}, dirs...)); err != nil {
		return fmt.Errorf("could not create directory, %w", err)
	}
	return nil
}
