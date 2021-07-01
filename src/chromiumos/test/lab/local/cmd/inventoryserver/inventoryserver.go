// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements inventory_service.proto (see proto for details)
package main

import (
	"log"
	"net"

	"go.chromium.org/chromiumos/config/go/test/lab/api"
	"google.golang.org/grpc"
)

// InventoryServer implementation of inventory_service.proto
type InventoryServer struct {
	logger *log.Logger
}

// newInventoryServer creates a new inventory service server to listen to rpc requests.
func newInventoryServer(l net.Listener, logger *log.Logger) (*grpc.Server, error) {
	s := &InventoryServer{
		logger: logger,
	}
	server := grpc.NewServer()
	api.RegisterInventoryServiceServer(server, s)
	logger.Println("inventoryservice listening to requests at ", l.Addr().String())
	return server, nil
}

func (s *InventoryServer) GetDutTopology(req *api.GetDutTopologyRequest, stream api.InventoryService_GetDutTopologyServer) error {
	s.logger.Println("Received api.GetDutTopology: ", *req)
	return stream.Send(&api.GetDutTopologyResponse{})
}
