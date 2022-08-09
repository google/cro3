// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// GRPC Server impl
package cli

import (
	"chromiumos/lro"
	common_utils "chromiumos/test/provision/v2/common-utils"
	firmwareservice "chromiumos/test/provision/v2/fw-provision/service"
	state_machine "chromiumos/test/provision/v2/fw-provision/state-machine"
	"context"
	"errors"
	"fmt"
	"log"
	"net"

	"go.chromium.org/chromiumos/config/go/test/api"
	api1 "go.chromium.org/chromiumos/config/go/test/lab/api"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"google.golang.org/grpc"
)

type FWProvisionServer struct {
	log        *log.Logger
	inputProto *api.ProvisionFirmwareRequest
	listenPort int

	dutClient   common_utils.ServiceAdapterInterface
	servoClient api.ServodServiceClient
	fwService   *firmwareservice.FirmwareService
	manager     *lro.Manager
}

func ipEndpointToHostPort(i *api1.IpEndpoint) (string, error) {
	if len(i.GetAddress()) == 0 {
		return "", errors.New("IpEndpoint missing address")
	}
	if i.GetPort() == 0 {
		return "", errors.New("IpEndpoint missing port")
	}
	return fmt.Sprintf("%v:%v", i.GetAddress(), i.GetPort()), nil
}

func NewFWProvisionServer(listenPort int, log *log.Logger, inputProto *api.ProvisionFirmwareRequest) (*FWProvisionServer, func(), error) {
	var conns []*grpc.ClientConn
	closer := func() {
		for _, conn := range conns {
			conn.Close()
		}
		conns = nil
	}

	dutServAddr, err := ipEndpointToHostPort(inputProto.GetDutServerAddress())
	if err != nil {
		return nil, nil, fmt.Errorf("failed to parse IpEndpoint of Dut Server: %w", err)
	}
	dutConn, err := grpc.Dial(dutServAddr, grpc.WithInsecure())
	if err != nil {
		return nil, nil, fmt.Errorf("failed to connect to dut-service, %s", err)
	}
	conns = append(conns, dutConn)
	dutAdapter := common_utils.NewServiceAdapter(api.NewDutServiceClient(dutConn), false /*noReboot*/)

	var servodServiceClient api.ServodServiceClient
	if inputProto.GetUseServo() {
		crosServodAddr, err := ipEndpointToHostPort(inputProto.GetCrosServodAddress())
		if err != nil {
			return nil, nil, fmt.Errorf("failed to parse IpEndpoint of Dut Server: %w", err)
		}
		servodConn, err := grpc.Dial(crosServodAddr, grpc.WithInsecure())
		conns = append(conns, servodConn)
		if err != nil {
			return nil, nil, fmt.Errorf("failed to connect to dut-service, %s", err)
		}
		conns = append(conns, servodConn)
		servodServiceClient = api.NewServodServiceClient(servodConn)
	}

	ctx := context.Background()
	fwService, err := firmwareservice.NewFirmwareService(ctx, dutAdapter, servodServiceClient, inputProto)
	if err != nil {
		log.Fatalf("Failed to initialize Firmware Service: %v", err)
		return nil, nil, err
	}

	return &FWProvisionServer{
		dutClient:   dutAdapter,
		servoClient: servodServiceClient,

		fwService: fwService,

		listenPort: listenPort,
		log:        log,
	}, closer, nil
}

func (ps *FWProvisionServer) Start() error {
	l, err := net.Listen("tcp", fmt.Sprintf(":%d", ps.listenPort))
	if err != nil {
		return fmt.Errorf("failed to create listener at %d", ps.listenPort)
	}
	ps.manager = lro.New()
	defer ps.manager.Close()
	server := grpc.NewServer()
	api.RegisterFirmwareProvisionServiceServer(server, ps)
	longrunning.RegisterOperationsServer(server, ps.manager)
	ps.log.Println("provisionservice listen to request at ", l.Addr().String())
	return server.Serve(l)
}

func (ps *FWProvisionServer) Provision(ctx context.Context, req *api.ProvisionFirmwareRequest) (*longrunning.Operation, error) {
	ps.log.Println("Received api.ProvisionFirmwareRequest: ", *req)
	op := ps.manager.NewOperation()
	response := api.InstallResponse{}

	// Execute state machine
	cs := state_machine.NewFirmwarePrepareState(ps.fwService)
	var err error
	for cs != nil {
		if err = cs.Execute(ctx); err != nil {
			break
		}
		cs = cs.Next()
	}
	ps.manager.SetResult(op.Name, &response)

	if err == nil {
		log.Println("Finished Successfuly!")
	} else {
		log.Println("Finished with error:", err)
	}
	return op, nil
}
