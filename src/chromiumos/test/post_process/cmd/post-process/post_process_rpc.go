// Copyright 2023 The ChromiumOS Authors
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

// PostTestServiceServer implementation of dut_service.proto
type PostTestServiceServer struct {
	logger    *log.Logger
	dutClient api.DutServiceClient
}

// NewServer creates an execution server.
func NewServer(logger *log.Logger, dutClient api.DutServiceClient) (*grpc.Server, func()) {
	s := &PostTestServiceServer{
		logger:    logger,
		dutClient: dutClient,
	}

	server := grpc.NewServer()
	var conns []*grpc.ClientConn
	closer := func() {
		for _, conn := range conns {
			conn.Close()
		}
		conns = nil
	}
	api.RegisterPostTestServiceServer(server, s)
	// longrunning.RegisterOperationsServer(server, s.manager)
	logger.Println("crostestservice listen to request at ")
	return server, closer
}

// RunActivity calls the parseAndRunCmds (post-process flow) in main.
func (s *PostTestServiceServer) RunActivity(ctx context.Context, req *api.RunActivityRequest) (*api.RunActivityResponse, error) {
	s.logger.Printf("Received GetFWInfo: %s", req)

	rspn, err := parseAndRunCmds(req, s.logger, s.dutClient)
	s.logger.Printf("After Parse")

	if err != nil {
		return nil, errors.Annotate(err, "PostService: failed to run post service").Err()
	}
	s.logger.Printf("PostService RPC Command was successful")
	s.logger.Printf("REturning %s", rspn)

	return rspn, nil
}
