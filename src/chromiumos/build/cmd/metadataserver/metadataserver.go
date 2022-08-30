// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements metadata_service.proto (see proto for details)
package main

import (
	"context"
	"log"
	"net"

	"go.chromium.org/chromiumos/config/go/build/api"
	"google.golang.org/grpc"
)

// MetadataServer implementation of metadata_service.proto
type MetadataServer struct {
	logger *log.Logger
}

// newMetadataServer creates a new metadata service server to listen to rpc requests.
func newMetadataServer(l net.Listener, logger *log.Logger) (*grpc.Server, error) {
	s := &MetadataServer{
		logger: logger,
	}
	server := grpc.NewServer()
	api.RegisterMetadataServiceServer(server, s)
	logger.Println("metadataservice listening to requests at ", l.Addr().String())
	return server, nil
}

func (s *MetadataServer) GetDeviceConfig(ctx context.Context,
	req *api.GetDeviceConfigRequest) (*api.GetDeviceConfigResponse, error) {
	s.logger.Println("Received api.GetDeviceConfig: ", req)
	s.logger.Println("TODO(shapiroc): implement")
	return &api.GetDeviceConfigResponse{}, nil
}
