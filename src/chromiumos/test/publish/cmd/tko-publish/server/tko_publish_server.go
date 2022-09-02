// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// GRPC Server impl
package server

import (
	"chromiumos/lro"
	"chromiumos/test/publish/cmd/common-utils/metadata"
	"chromiumos/test/publish/cmd/tko-publish/service"
	"context"
	"fmt"
	"log"
	"net"

	"go.chromium.org/chromiumos/config/go/test/api"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"
)

type TkoPublishServer struct {
	options *metadata.ServerMetadata
	manager *lro.Manager
	server  *grpc.Server
}

func NewTkoPublishServer(options *metadata.ServerMetadata) (*TkoPublishServer, func(), error) {
	var conns []*grpc.ClientConn
	closer := func() {
		for _, conn := range conns {
			conn.Close()
		}
		conns = nil
	}

	return &TkoPublishServer{
		options: options,
	}, closer, nil
}

func (ps *TkoPublishServer) Start() error {
	l, err := net.Listen("tcp", fmt.Sprintf(":%d", ps.options.Port))
	if err != nil {
		return fmt.Errorf("failed to create listener at %d", ps.options.Port)
	}

	ps.manager = lro.New()
	defer ps.manager.Close()

	ps.server = grpc.NewServer()
	api.RegisterGenericPublishServiceServer(ps.server, ps)
	longrunning.RegisterOperationsServer(ps.server, ps.manager)
	reflection.Register(ps.server)

	log.Println("tko-publish-service listen to request at ", l.Addr().String())
	return ps.server.Serve(l)
}

func (ps *TkoPublishServer) Publish(ctx context.Context, req *api.PublishRequest) (*longrunning.Operation, error) {
	log.Println("Received api.PublishRequest: ", req)
	op := ps.manager.NewOperation()
	out := &api.PublishResponse{
		Status: api.PublishResponse_STATUS_SUCCESS,
	}

	defer func() {
		ps.manager.SetResult(op.Name, out)
	}()

	gps, err := service.NewTkoPublishService(req)
	if err != nil {
		log.Printf("failed to create new tko publish service: %s", err)
		out.Status = api.PublishResponse_STATUS_INVALID_REQUEST
		out.Message = fmt.Sprintf("failed to create new tko publish service: %s", err.Error())
		return op, fmt.Errorf("failed to create new tko publish service: %s", err)
	}

	if err := gps.UploadToTko(context.Background()); err != nil {
		log.Printf("upload to tko failed: %s", err)
		out.Status = api.PublishResponse_STATUS_FAILURE
		out.Message = fmt.Sprintf("failed upload to tko: %s", err.Error())
		return op, fmt.Errorf("failed upload to tko: %s", err)
	}

	log.Println("Finished Successfuly!")
	return op, nil
}
