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
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"chromiumos/test/execution/cmd/testexecserver/internal/driver"
)

// TestExecServer implement a server that will run tests
type TestExecServer struct {
	Manager *lro.Manager
	logger  *log.Logger
	driver  string
}

// newTestExecServer creates a new test service server to listen to test requests.
func newTestExecServer(l net.Listener, logger *log.Logger, driver string) (*grpc.Server, error) {
	s := &TestExecServer{
		Manager: lro.New(),
		logger:  logger,
		driver:  driver,
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
	if req.Dut == nil || req.Dut.PrimaryHost == "" {
		s.Manager.SetError(op.Name, status.New(codes.InvalidArgument, "DUT is not defined"))
		return op, nil
	}
	var testDriver driver.Driver
	if s.driver == "tast" {
		testDriver = driver.NewTastDriver(s.logger, s.Manager, op.Name)
	}
	var tests []string
	for _, suite := range req.TestSuites {
		for _, tc := range suite.TestCaseIds.TestCaseIds {
			tests = append(tests, tc.Value)
		}
		// TO-DO Support Tags
	}
	if testDriver != nil {
		go testDriver.RunTests(ctx, "", req.Dut.PrimaryHost, tests)
	}
	return op, nil
}
