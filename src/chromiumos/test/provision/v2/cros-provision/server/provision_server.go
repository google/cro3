// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// GRPC Server impl
package server

import (
	"chromiumos/lro"
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/metadata"
	"chromiumos/test/provision/v2/cros-provision/service"
	state_machine "chromiumos/test/provision/v2/cros-provision/state-machine"
	"context"
	"fmt"
	"net"

	"go.chromium.org/chromiumos/config/go/test/api"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"google.golang.org/grpc"
)

type ProvisionServer struct {
	options   *metadata.ServerMetadata
	dutClient api.DutServiceClient
	manager   *lro.Manager
}

func NewProvisionServer(options *metadata.ServerMetadata) (*ProvisionServer, func(), error) {
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
	}, closer, nil
}

func (ps *ProvisionServer) Start() error {
	l, err := net.Listen("tcp", fmt.Sprintf(":%d", ps.options.Port))
	if err != nil {
		return fmt.Errorf("failed to create listener at %d", ps.options.Port)
	}
	ps.manager = lro.New()
	defer ps.manager.Close()
	server := grpc.NewServer()
	api.RegisterGenericProvisionServiceServer(server, ps)
	longrunning.RegisterOperationsServer(server, ps.manager)
	ps.options.Log.Println("provisionservice listen to request at ", l.Addr().String())
	return server.Serve(l)
}

func (sp *ProvisionServer) Install(ctx context.Context, req *api.InstallRequest) (*longrunning.Operation, error) {
	sp.options.Log.Println("Received api.InstallCrosRequest: ", *req)
	op := sp.manager.NewOperation()
	response := api.InstallResponse{}

	fr, err := sp.installCros(ctx, req)
	if err != nil {
		sp.options.Log.Fatalf("failed provision, %s", err)
	}
	response.Status = fr
	sp.manager.SetResult(op.Name, &response)
	return op, nil
}

// installCros installs a specified version of Chrome OS on the DUT, along
// with any specified DLCs.
func (ps *ProvisionServer) installCros(ctx context.Context, req *api.InstallRequest) (api.InstallResponse_Status, error) {
	ps.options.Log.Println("Received api.InstallRequest: ", *req)
	cs, err := service.NewCrOSService(ps.options.Dut, ps.dutClient, req)
	if err != nil {
		return api.InstallResponse_STATUS_INVALID_REQUEST, err
	}
	cis := state_machine.NewCrOSInitState(*cs)

	return common_utils.ExecuteStateMachine(ctx, cis)
}
