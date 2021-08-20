// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements publish_service.proto (see proto for details)
package main

import (
	"chromiumos/lro"
	"chromiumos/test/publish/cmd/publishserver/storage"
	"context"
	"log"
	"net"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/grpc"
)

// PublishServiceServer implementation of publish_service.proto
type PublishServiceServer struct {
	manager  *lro.Manager
	logger   *log.Logger
	gsClient storage.GSClientInterface
}

// newPublishServiceServer creates a new publish service server to listen to rpc requests.
func newPublishServiceServer(l net.Listener, logger *log.Logger, gcpCredentials string) (*grpc.Server, func(), error) {
	gsClient, err := storage.NewGSClient(context.Background(), gcpCredentials)
	if err != nil {
		return nil, nil, err
	}
	s := &PublishServiceServer{
		manager:  lro.New(),
		logger:   logger,
		gsClient: gsClient,
	}

	server := grpc.NewServer()
	destructor := func() {
		s.manager.Close()
		s.gsClient.Close()
	}

	api.RegisterPublishServiceServer(server, s)
	logger.Println("publishservice listen to request at ", l.Addr().String())
	return server, destructor, nil
}

// UploadToGS uploads the designated folder to the provided Google Cloud Storage
// bucket/object
func (s *PublishServiceServer) UploadToGS(ctx context.Context, req *api.UploadToGSRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.UploadToGSRequest: ", *req)
	op := s.manager.NewOperation()
	if err := s.gsClient.Upload(ctx, req.LocalDirectory, req.GsDirectory); err != nil {
		return nil, err
	}
	s.manager.SetResult(op.Name, &api.UploadToGSResponse{
		GsUrl: req.GsDirectory,
	})
	return op, nil
}
