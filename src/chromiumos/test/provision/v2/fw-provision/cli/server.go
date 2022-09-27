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
	// dutAdapter provides an interface to manipulate DUT via cros-dut
	// service. Its address may be specified either when server is created,
	// or later in user's ProvisionFirmwareRequest
	dutAdapter common_utils.ServiceAdapterInterface

	// servoClient provides an interface to manipulate DUT via cros-servod
	// service. Its address may be specified either when server is created,
	// or later in user's ProvisionFirmwareRequest
	servoClient api.ServodServiceClient

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

func NewFWProvisionServer(listenPort int, log *log.Logger, dutAdapter common_utils.ServiceAdapterInterface, servoClient api.ServodServiceClient) (*FWProvisionServer, func(), error) {
	return &FWProvisionServer{
		listenPort:  listenPort,
		log:         log,
		dutAdapter:  dutAdapter,
		servoClient: servoClient,
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
	ps.log.Printf("Received api.ProvisionFirmwareRequest: %#v\n", req)
	log.Printf("Received api.ProvisionFirmwareRequest: %#v\n", req)
	op := ps.manager.NewOperation()
	response := api.ProvisionFirmwareResponse{}

	if err := ps.validateProtoInputs(req); err != nil {
		response.Status = api.ProvisionFirmwareResponse_STATUS_INVALID_REQUEST
		ps.manager.SetResult(op.Name, &response)
		return nil, firmwareservice.InvalidRequestErr(err.Error())
	}

	var dutAdapter *common_utils.ServiceAdapter
	var err error
	if !req.GetUseServo() && ps.dutAdapter == nil {
		// the (ps.dutAdapter == nil) check ensures that cros-dut address
		// specified during fw-provisioning startup is preferred.
		dutAdapter, err = connectToDutServer(req.GetDutServerAddress())
		if err != nil {
			response.Status = api.ProvisionFirmwareResponse_STATUS_INVALID_REQUEST
			ps.manager.SetResult(op.Name, &response)
			log.Fatalln(err)
			return nil, firmwareservice.InvalidRequestErr(err.Error())
		}
		ps.dutAdapter = dutAdapter
	}

	var servodServiceClient api.ServodServiceClient
	if req.GetUseServo() && ps.servoClient == nil {
		// the (ps.servoClient == nil) check ensures that cros-servod address
		// specified during fw-provisioning startup is preferred.
		servodServiceClient, err = connectToCrosServod(req.GetCrosServodAddress())
		if err != nil {
			response.Status = api.ProvisionFirmwareResponse_STATUS_INVALID_REQUEST
			ps.manager.SetResult(op.Name, &response)
			log.Fatalln(err)
			return nil, firmwareservice.InvalidRequestErr(err.Error())
		}
		ps.servoClient = servodServiceClient
	}

	fwService, err := firmwareservice.NewFirmwareService(ctx, ps.dutAdapter, ps.servoClient, req)
	if err != nil {
		response.Status = api.ProvisionFirmwareResponse_STATUS_INVALID_REQUEST
		ps.manager.SetResult(op.Name, &response)
		log.Fatalf("Failed to initialize Firmware Service: %v", err)
		return nil, firmwareservice.InvalidRequestErr(err.Error())
	}

	// Execute state machine
	cs := state_machine.NewFirmwarePrepareState(fwService)
	for cs != nil {
		if err = cs.Execute(ctx); err != nil {
			break
		}
		cs = cs.Next()
	}

	if err == nil {
		log.Println("Finished Successfuly!")
		response.Status = api.ProvisionFirmwareResponse_STATUS_OK
		ps.manager.SetResult(op.Name, &response)
	} else {
		response.Status = api.ProvisionFirmwareResponse_STATUS_UPDATE_FIRMWARE_FAILED
		ps.manager.SetResult(op.Name, &response)
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
	if req.GetSimpleRequest() == nil && req.GetDetailedRequest() == nil {
		return errors.New("ProvisionFirmwareRequest: SimpleRequest or DetailedRequest is required")
	}
	return nil
}
