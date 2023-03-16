// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// GRPC Server impl
package server

import (
	"chromiumos/lro"
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/common-utils/metadata"
	"chromiumos/test/util/portdiscovery"

	"context"
	"fmt"
	"net"

	"go.chromium.org/chromiumos/config/go/test/api"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"google.golang.org/grpc"
	"google.golang.org/protobuf/types/known/anypb"
)

type ProvisionServer struct {
	options   *metadata.ServerMetadata
	dutClient api.DutServiceClient
	manager   *lro.Manager
	executor  ProvisionExecutor
}

func NewProvisionServer(options *metadata.ServerMetadata, executor ProvisionExecutor) (*ProvisionServer, func(), error) {
	var conns []*grpc.ClientConn
	closer := func() {
		for _, conn := range conns {
			conn.Close()
		}
		conns = nil
	}
	dutConn, err := grpc.Dial(options.DutAddress, grpc.WithInsecure())
	if err != nil {
		return nil, closer, fmt.Errorf("failed to connect to dut-service, %s", err)
	}
	conns = append(conns, dutConn)

	return &ProvisionServer{
		options:   options,
		dutClient: api.NewDutServiceClient(dutConn),
		executor:  executor,
	}, closer, nil
}

func (ps *ProvisionServer) Start() error {
	l, err := net.Listen("tcp", fmt.Sprintf(":%d", ps.options.Port))
	if err != nil {
		return fmt.Errorf("failed to create listener at %d", ps.options.Port)
	}

	// Write port number to ~/.cftmeta for go/cft-port-discovery
	err = portdiscovery.WriteServiceMetadata("provision", l.Addr().String(), ps.options.Log)
	if err != nil {
		ps.options.Log.Println("Warning: error when writing to metadata file: ", err)
	}

	ps.manager = lro.New()
	defer ps.manager.Close()
	server := grpc.NewServer()
	api.RegisterGenericProvisionServiceServer(server, ps)
	longrunning.RegisterOperationsServer(server, ps.manager)
	ps.options.Log.Println("provisionservice listen to request at ", l.Addr().String())
	return server.Serve(l)
}

func (ps *ProvisionServer) Install(ctx context.Context, req *api.InstallRequest) (*longrunning.Operation, error) {
	ps.options.Log.Println("Received api.InstallCrosRequest: ", req)
	op := ps.manager.NewOperation()
	response := api.InstallResponse{}

	installResp, md, err := ps.installTarget(ctx, req)
	if err != nil {
		ps.options.Log.Printf("failed provision, %s", err)
	}
	response.Status = installResp
	response.Metadata = md
	ps.manager.SetResult(op.Name, &response)
	ps.options.Log.Printf("Provision set OP Response to:%s ", &response)
	// Note: Do not return the err here, as it causes the op response to not be set.
	// Since the op will carry the failure reason, just set the op.
	return op, nil
}

// installTarget installs a specified version of the software on the target, along
// with any specified DLCs.
func (ps *ProvisionServer) installTarget(ctx context.Context, req *api.InstallRequest) (api.InstallResponse_Status, *anypb.Any, error) {
	ps.options.Log.Println("Received api.InstallRequest: ", req)
	fs, err := ps.executor.GetFirstState(ps.options.Dut, ps.dutClient, req)
	if err != nil {
		return api.InstallResponse_STATUS_INVALID_REQUEST, nil, err
	}

	return common_utils.ExecuteStateMachine(ctx, fs, ps.options.Log)
}
