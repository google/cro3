// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements dut_service.proto (see proto for details)
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

// DutServer implementation of dut_service.proto
type DutServer struct {
	Manager *lro.Manager
	logger  *log.Logger
}

// newDutServer creates a new dut service server to listen to rpc requests.
func newDutServer(l net.Listener, logger *log.Logger) (*grpc.Server, error) {
	s := &DutServer{
		Manager: lro.New(),
		logger:  logger,
	}
	defer s.Manager.Close()
	server := grpc.NewServer()
	api.RegisterDutServiceServer(server, s)
	longrunning.RegisterOperationsServer(server, s.Manager)
	logger.Println("dutservice listen to request at ", l.Addr().String())
	return server, nil
}

// ProvisionDut installs a specified version of Chrome OS on the DUT, along
// with any specified DLCs.
//
// If the DUT is already on the specified version of Chrome OS, the OS will
// not be provisioned.
//
// If the DUT already has the specified list of DLCs, only the missing DLCs
// will be provisioned.
func (s *DutServer) ProvisionDut(ctx context.Context, req *api.ProvisionDutRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.ProvisionDutRequest: ", *req)
	op := s.Manager.NewOperation()
	s.Manager.SetResult(op.Name, &api.ProvisionDutResponse{})
	return op, nil
}

// ProvisionLacros installs a specified version of Lacros on the DUT.
//
// If the DUT already has the specified version of Lacros, Lacros will not be
// provisioned.
func (s *DutServer) ProvisionLacros(ctx context.Context, req *api.ProvisionLacrosRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.ProvisionLacrosRequest: ", *req)
	op := s.Manager.NewOperation()
	s.Manager.SetResult(op.Name, &api.ProvisionLacrosResponse{})
	return op, nil
}

// ProvisionAsh installs a specified version of ash-chrome on the DUT.
//
// This directly overwrites the version of ash-chrome on the current root
// disk partition.
func (s *DutServer) ProvisionAsh(ctx context.Context, req *api.ProvisionAshRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.ProvisionAshRequest: ", *req)
	op := s.Manager.NewOperation()
	s.Manager.SetResult(op.Name, &api.ProvisionAshResponse{})
	return op, nil
}

// ProvisionArc installs a specified version of ARC on the DUT.
//
// This directly overwrites the version of ARC on the current root
// disk partition.
func (s *DutServer) ProvisionArc(ctx context.Context, req *api.ProvisionArcRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.ProvisionArcRequest: ", *req)
	op := s.Manager.NewOperation()
	s.Manager.SetResult(op.Name, &api.ProvisionArcResponse{})
	return op, nil
}
