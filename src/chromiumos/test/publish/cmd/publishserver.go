// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements publish_service.proto (see proto for details)
package main

import (
	"chromiumos/lro"
	"context"
	"log"
	"net"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"
)

// PublishServiceServer implementation of publish_service.proto
type PublishServiceServer struct {
	manager *lro.Manager
	logger  *log.Logger
}

// newPublishServiceServer creates a new publish service server to listen to rpc requests.
func newPublishServiceServer(l net.Listener, logger *log.Logger) (*grpc.Server, func()) {
	s := &PublishServiceServer{
		manager: lro.New(),
		logger:  logger,
	}

	server := grpc.NewServer()
	destructor := func() {
		s.manager.Close()
	}

	api.RegisterPublishServiceServer(server, s)
	logger.Println("publishservice listen to request at ", l.Addr().String())
	return server, destructor
}

// UploadToGS uploads the designated folder to the provided Google Cloud Storage
// bucket/object
//
// TODO(jaquesc): Implement this
func (s *PublishServiceServer) UploadToGS(ctx context.Context, req *api.UploadToGSRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.UploadToGSRequest: ", *req)
	s.logger.Println("TODO(jaquesc): Implement")
	op := s.manager.NewOperation()
	s.manager.SetResult(op.Name, &api.UploadToGSResponse{})
	return op, nil
}
