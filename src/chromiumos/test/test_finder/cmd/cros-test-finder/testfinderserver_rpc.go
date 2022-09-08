// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

import (
	"context"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"
	"google.golang.org/grpc"
)

// TestFinderServiceServer implementation of dut_service.proto
type TestFinderServiceServer struct {
	logger      *log.Logger
	metadatadir string
}

// NewServer creates an execution server.
func NewServer(logger *log.Logger, metadatadir string) (*grpc.Server, func()) {
	s := &TestFinderServiceServer{
		logger: logger,

		metadatadir: metadatadir,
	}

	server := grpc.NewServer()
	var conns []*grpc.ClientConn
	closer := func() {
		for _, conn := range conns {
			conn.Close()
		}
		conns = nil
	}
	api.RegisterTestFinderServiceServer(server, s)
	// longrunning.RegisterOperationsServer(server, s.manager)
	logger.Println("crostestservice listen to request at ")
	return server, closer
}

// FindTests calls the innerMain (test-finder flow) in main.
func (s *TestFinderServiceServer) FindTests(ctx context.Context, req *api.CrosTestFinderRequest) (*api.CrosTestFinderResponse, error) {
	s.logger.Println("Received api.CacheRequest: ", req)

	rspn, err := innerMain(s.logger, req, s.metadatadir)
	if err != nil {
		return nil, errors.Annotate(err, "FindTests: failed to find tests").Err()
	}
	s.logger.Printf("FindTest RPC Command was successful")
	return rspn, nil
}
