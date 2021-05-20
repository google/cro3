// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package main implements the executionservice server
package main

import (
	"context"
	"log"
	"net"

	"chromiumos/lro"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"
)

// TestExecServer implement a server that will run tests
type TestExecServer struct {
	Manager *lro.Manager
	logger  *log.Logger
}

// newTestExecServer creates a new test service server to listen to test requests.
func newTestExecServer(l net.Listener, logger *log.Logger) (*grpc.Server, error) {
	s := &TestExecServer{
		Manager: lro.New(),
		logger:  logger,
	}
	defer s.Manager.Close()
	server := grpc.NewServer()
	api.RegisterExecutionServiceServer(server, s)
	longrunning.RegisterOperationsServer(server, s.Manager)
	logger.Println("executionservice listen to request at ", l.Addr().String())
	return server, nil
}

// RunTests runs the requested tests.
func (s *TestExecServer) RunTests(ctx context.Context, req *api.RunTestsRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.RunTestsRequest: ", *req)
	op := s.Manager.NewOperation()
	s.Manager.SetResult(op.Name, &api.RunTestsResponse{})
	return op, nil
}
