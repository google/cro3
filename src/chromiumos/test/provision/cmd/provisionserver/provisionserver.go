// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements provision_service.proto (see proto for details)
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

// ProvisionServer implementation of provision_service.proto
type ProvisionServer struct {
	Manager *lro.Manager
	logger  *log.Logger
}

// newProvisionServer creates a new provision service server to listen to rpc requests.
func newProvisionServer(l net.Listener, logger *log.Logger) (*grpc.Server, error) {
	s := &ProvisionServer{
		Manager: lro.New(),
		logger:  logger,
	}
	defer s.Manager.Close()
	server := grpc.NewServer()
	api.RegisterProvisionServiceServer(server, s)
	longrunning.RegisterOperationsServer(server, s.Manager)
	logger.Println("provisionservice listen to request at ", l.Addr().String())
	return server, nil
}

// InstallCros installs a specified version of Chrome OS on the DUT, along
// with any specified DLCs.
//
// If the DUT is already on the specified version of Chrome OS, the OS will
// not be provisioned.
//
// If the DUT already has the specified list of DLCs, only the missing DLCs
// will be provisioned.
func (s *ProvisionServer) InstallCros(ctx context.Context, req *api.InstallCrosRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.InstallCrosRequest: ", *req)
	op := s.Manager.NewOperation()
	s.Manager.SetResult(op.Name, &api.InstallCrosResponse{})
	return op, nil
}

// InstallLacros installs a specified version of Lacros on the DUT.
//
// If the DUT already has the specified version of Lacros, Lacros will not be
// provisioned.
func (s *ProvisionServer) InstallLacros(ctx context.Context, req *api.InstallLacrosRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.InstallLacrosRequest: ", *req)
	op := s.Manager.NewOperation()
	s.Manager.SetResult(op.Name, &api.InstallLacrosResponse{})
	return op, nil
}

// InstallAsh installs a specified version of ash-chrome on the DUT.
//
// This directly overwrites the version of ash-chrome on the current root
// disk partition.
func (s *ProvisionServer) InstallAsh(ctx context.Context, req *api.InstallAshRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.InstallAshRequest: ", *req)
	op := s.Manager.NewOperation()
	s.Manager.SetResult(op.Name, &api.InstallAshResponse{})
	return op, nil
}

// InstallArc installs a specified version of ARC on the DUT.
//
// This directly overwrites the version of ARC on the current root
// disk partition.
func (s *ProvisionServer) InstallArc(ctx context.Context, req *api.InstallArcRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.InstallArcRequest: ", *req)
	op := s.Manager.NewOperation()
	s.Manager.SetResult(op.Name, &api.InstallArcResponse{})
	return op, nil
}
