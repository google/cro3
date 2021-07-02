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
	logger      *log.Logger
	dutTopology *api.DutTopology
}

// Optional arguments (passed during startup that control serving behavior)
type Options struct {
	DutAddress string
	DutPort    int
}

// newInventoryServer creates a new inventory service server to listen to rpc requests.
func newInventoryServer(l net.Listener, logger *log.Logger, options *Options) (*grpc.Server, error) {
	dutTopology := &api.DutTopology{}
	if len(options.DutAddress) != 0 {
		dutTopology = &api.DutTopology{
			Id: &api.DutTopology_Id{
				Value: options.DutAddress,
			},
			Dut: &api.Dut{
				Id: &api.Dut_Id{
					Value: options.DutAddress,
				},
				DutType: &api.Dut_Chromeos{
					Chromeos: &api.Dut_ChromeOS{
						Ssh: &api.IpEndpoint{
							Address: options.DutAddress,
							Port:    int32(options.DutPort),
						},
					},
				},
			},
		}
	}

	s := &InventoryServer{
		logger:      logger,
		dutTopology: dutTopology,
	}
	server := grpc.NewServer()
	api.RegisterInventoryServiceServer(server, s)
	logger.Println("inventoryservice listening to requests at ", l.Addr().String())
	return server, nil
}

func (s *InventoryServer) GetDutTopology(req *api.GetDutTopologyRequest, stream api.InventoryService_GetDutTopologyServer) error {
	s.logger.Println("Received api.GetDutTopology: ", *req)
	return stream.Send(&api.GetDutTopologyResponse{
		Result: &api.GetDutTopologyResponse_Success_{
			Success: &api.GetDutTopologyResponse_Success{
				DutTopology: s.dutTopology,
			},
		},
	})
}
