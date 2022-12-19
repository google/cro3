// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// GRPC Server impl
package server

import (
	"chromiumos/lro"
	"chromiumos/test/publish/cmd/common-utils/metadata"
	"chromiumos/test/publish/cmd/cpcon-publish/service"
	"context"
	"fmt"
	"log"
	"net"

	"go.chromium.org/chromiumos/config/go/test/api"

	"chromiumos/test/util/portdiscovery"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"google.golang.org/grpc"
	"google.golang.org/grpc/reflection"
)

type CpconPublishServer struct {
	options *metadata.ServerMetadata
	manager *lro.Manager
	server  *grpc.Server
}

func NewCpconPublishServer(options *metadata.ServerMetadata) (*CpconPublishServer, func(), error) {
	var conns []*grpc.ClientConn
	closer := func() {
		for _, conn := range conns {
			conn.Close()
		}
		conns = nil
	}

	return &CpconPublishServer{
		options: options,
	}, closer, nil
}

func (ps *CpconPublishServer) Start() error {
	l, err := net.Listen("tcp", fmt.Sprintf(":%d", ps.options.Port))
	if err != nil {
		return fmt.Errorf("failed to create listener at %d", ps.options.Port)
	}

	// Write port number to ~/.cftmeta for go/cft-port-discovery
	err = portdiscovery.WriteServiceMetadata("cpcon-publish", l.Addr().String(), nil)
	if err != nil {
		log.Println("Warning: error when writing to metadata file: ", err)
	}

	ps.manager = lro.New()
	defer ps.manager.Close()

	ps.server = grpc.NewServer()
	api.RegisterGenericPublishServiceServer(ps.server, ps)
	longrunning.RegisterOperationsServer(ps.server, ps.manager)
	reflection.Register(ps.server)

	log.Println("cpcon-publish-service listen to request at ", l.Addr().String())
	return ps.server.Serve(l)
}

func (ps *CpconPublishServer) Publish(ctx context.Context, req *api.PublishRequest) (*longrunning.Operation, error) {
	log.Println("Received api.PublishRequest: ", req)
	op := ps.manager.NewOperation()
	out := &api.PublishResponse{
		Status: api.PublishResponse_STATUS_SUCCESS,
	}

	defer func() {
		ps.manager.SetResult(op.Name, out)
	}()

	gps, err := service.NewCpconPublishService(req)
	if err != nil {
		log.Printf("failed to create new cpcon publish service: %s", err)
		out.Status = api.PublishResponse_STATUS_INVALID_REQUEST
		out.Message = fmt.Sprintf("failed to create new cpcon publish service: %s", err.Error())
		return op, fmt.Errorf("failed to create new cpcon publish service: %s", err)
	}

	if err := gps.UploadToCpcon(context.Background()); err != nil {
		log.Printf("upload to cpcon failed: %s", err)
		out.Status = api.PublishResponse_STATUS_FAILURE
		out.Message = fmt.Sprintf("failed upload to cpcon: %s", err.Error())
		return op, fmt.Errorf("failed upload to cpcon: %s", err)
	}

	log.Println("Finished Successfuly!")
	return op, nil
}
