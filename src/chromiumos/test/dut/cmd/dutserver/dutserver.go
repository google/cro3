// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements dut_service.proto (see proto for details)
package main

import (
	"chromiumos/lro"
	"log"
	"net"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"
)

// DutServiceServer implementation of dut_service.proto
type DutServiceServer struct {
	Manager *lro.Manager
	logger  *log.Logger
}

// Create a new provision service server to listen to rpc requests.
func newDutServiceServer(l net.Listener, logger *log.Logger) (*grpc.Server, error) {
	s := &DutServiceServer{
		Manager: lro.New(),
		logger:  logger,
	}
	defer s.Manager.Close()
	server := grpc.NewServer()
	api.RegisterDutServiceServer(server, s)
	logger.Println("dutservice listen to request at ", l.Addr().String())
	return server, nil
}

// Remotely execute a command on the DUT.
func (s *DutServiceServer) ExecCommand(req *api.ExecCommandRequest, stream api.DutService_ExecCommandServer) error {
	s.logger.Println("Received api.ExecCommandRequest: ", *req)
	return stream.Send(&api.ExecCommandResponse{})
}

// Remotely fetch crashes from the DUT.
func (s *DutServiceServer) FetchCrashes(req *api.FetchCrashesRequest, stream api.DutService_FetchCrashesServer) error {
	s.logger.Println("Received api.FetchCrashesRequest: ", *req)
	return stream.Send(&api.FetchCrashesResponse{})
}
