// Copyright 2022 The ChromiumOS Authors
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
	listenPort int

	manager *lro.Manager
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

func NewFWProvisionServer(listenPort int, log *log.Logger) (*FWProvisionServer, func(), error) {
	return &FWProvisionServer{
		listenPort: listenPort,
		log:        log,
	}, nil, nil
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
	if err := ps.validateProtoInputs(req); err != nil {
		return nil, fmt.Errorf("failed to validate ProvisionFirmwareRequest: %w", err)
	}

	var dutAdapter common_utils.ServiceAdapter
	if !req.GetUseServo() {
		dutServAddr, err := ipEndpointToHostPort(req.GetDutServerAddress())
		if err != nil {
			return nil, fmt.Errorf("failed to parse IpEndpoint of Dut Server: %w", err)
		}
		dutConn, err := grpc.Dial(dutServAddr, grpc.WithInsecure())
		if err != nil {
			return nil, fmt.Errorf("failed to connect to dut-service, %s", err)
		}
		defer dutConn.Close()
		dutAdapter = common_utils.NewServiceAdapter(api.NewDutServiceClient(dutConn), false /*noReboot*/)
	}

	var servodServiceClient api.ServodServiceClient
	if req.GetUseServo() {
		crosServodAddr, err := ipEndpointToHostPort(req.GetCrosServodAddress())
		if err != nil {
			return nil, fmt.Errorf("failed to parse IpEndpoint of cros-servod: %w", err)
		}
		servodConn, err := grpc.Dial(crosServodAddr, grpc.WithInsecure())
		if err != nil {
			return nil, fmt.Errorf("failed to connect to cros-servod, %s", err)
		}
		defer servodConn.Close()
		servodServiceClient = api.NewServodServiceClient(servodConn)
	}

	fwService, err := firmwareservice.NewFirmwareService(ctx, dutAdapter, servodServiceClient, req)
	if err != nil {
		log.Fatalf("Failed to initialize Firmware Service: %v", err)
		return nil, err
	}

	ps.log.Println("Received api.ProvisionFirmwareRequest: ", *req)
	op := ps.manager.NewOperation()
	response := api.InstallResponse{}

	// Execute state machine
	cs := state_machine.NewFirmwarePrepareState(fwService)
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

// validateProtoInputs ensures the proto part of the CLI input is valid
func (cc *FWProvisionServer) validateProtoInputs(req *api.ProvisionFirmwareRequest) error {
	if len(req.Board) == 0 {
		return errors.New("ProvisionFirmwareRequest: Board field is required ")
	}
	if len(req.Model) == 0 {
		return errors.New("ProvisionFirmwareRequest: Model field is required ")
	}
	if req.UseServo {
		if req.CrosServodAddress == nil {
			return errors.New("ProvisionFirmwareRequest: CrosServodAddress is required when UseServo=true")
		}
	}
	if req.DutServerAddress == nil {
		return errors.New("ProvisionFirmwareRequest: DutServerAddress is required")
	}
	if req.GetSimpleRequest() == nil && req.GetDetailedRequest() == nil {
		return errors.New("ProvisionFirmwareRequest: SimpleRequest or DetailedRequest is required")
	}
	return nil
}
