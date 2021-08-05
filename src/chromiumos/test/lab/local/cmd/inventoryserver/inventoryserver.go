// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements inventory_service.proto (see proto for details)
package main

import (
	"bytes"
	"errors"
	"io/ioutil"
	"log"
	"net"

	"github.com/golang/protobuf/jsonpb"
	"github.com/golang/protobuf/proto"
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
	// File path to a serialized jsonproto payload of DutTopology.
	// This allows local complex lab setups (e.g. multi-dut) for local testing.
	DutTopologyConfigPath string
}

// readJsonpb reads the jsonpb at path into m.
func readJsonpb(path string, m proto.Message) error {
	b, err := ioutil.ReadFile(path)
	if err != nil {
		return err
	}
	return jsonpb.Unmarshal(bytes.NewReader(b), m)
}

// newInventoryServer creates a new inventory service server to listen to rpc requests.
func newInventoryServer(l net.Listener, logger *log.Logger, options *Options) (*grpc.Server, error) {
	dutTopology := &api.DutTopology{}

	dutAddress := len(options.DutAddress) != 0
	dutTopoConfig := len(options.DutTopologyConfigPath) != 0

	if dutAddress && dutTopoConfig {
		return nil, errors.New("DutAddress and DutTopologyConfigOptions options are mutally exclusive")
	}

	if dutTopoConfig {
		if err := readJsonpb(options.DutTopologyConfigPath, dutTopology); err != nil {
			return nil, err
		}
	} else if dutAddress {
		dutTopology = &api.DutTopology{
			Id: &api.DutTopology_Id{
				Value: options.DutAddress,
			},
			Duts: []*api.Dut{
				{
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
