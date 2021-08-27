// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Service interfaces bases
package services

import (
	"context"
	"fmt"
	"time"

	"github.com/golang/protobuf/ptypes"
	"go.chromium.org/chromiumos/config/go/api/test/tls"
	longrunning2 "go.chromium.org/chromiumos/config/go/api/test/tls/dependencies/longrunning"
	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"

	"chromiumos/lroold"
)

// ServiceAdapters are used to interface with a DUT
type ServiceAdapterInterface interface {
	RunCmd(ctx context.Context, cmd string, args []string) (string, error)
	Restart(ctx context.Context) error
	PathExists(ctx context.Context, path string) (bool, error)
	CopyData(ctx context.Context, url string) (string, error)
	DeleteDirectory(ctx context.Context, dir string) error
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
		return "", fmt.Errorf("execution fail: %s\n", err)
	}
	// Expecting single stream result
	feature, err := stream.Recv()
	if err != nil {
		return "", fmt.Errorf("execution single stream result: %s\n", err)
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

// CopyData caches a file for a DUT and returns the URL to use.
// NOTE: In the future the hope is to not use TLS for this. This is a placeholder until then.
func (s ServiceAdapter) CopyData(ctx context.Context, url string) (string, error) {
	wiringClient := tls.WiringClient(tls.NewWiringClient(s.wiringConn))
	wireOperation, err := wiringClient.CacheForDut(ctx, &tls.CacheForDutRequest{
		Url:     url,
		DutName: s.dutName,
	})
	if err != nil {
		return "", err
	}

	waitOperation, err := lroold.Wait(ctx, longrunning2.NewOperationsClient(s.wiringConn), wireOperation.Name)
	if err != nil {
		return "", fmt.Errorf("cacheForDut: failed to wait for CacheForDut, %s", err)
	}

	if s := waitOperation.GetError(); s != nil {
		return "", fmt.Errorf("cacheForDut: failed to get CacheForDut, %s", s)
	}

	a := waitOperation.GetResponse()
	if a == nil {
		return "", fmt.Errorf("cacheForDut: failed to get CacheForDut response for URL=%s and Name=%s", url, s.dutName)
	}

	resp := &tls.CacheForDutResponse{}
	if err := ptypes.UnmarshalAny(a, resp); err != nil {
		return "", fmt.Errorf("cacheForDut: unexpected response from CacheForDut, %v", a)
	}

	return resp.GetUrl(), nil
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
