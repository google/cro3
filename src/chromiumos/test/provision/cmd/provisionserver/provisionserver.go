// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements provision_service.proto (see proto for details)
package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"time"

	"chromiumos/lro"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/ashservice"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/crosservice"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/lacrosservice"

	"go.chromium.org/chromiumos/config/go/api/test/tls"
	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/genproto/googleapis/rpc/errdetails"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"
)

// ProvisionServer implementation of provision_service.proto
type ProvisionServer struct {
	Manager    *lro.Manager
	logger     *log.Logger
	dutName    string
	dutClient  api.DutServiceClient
	wiringConn *grpc.ClientConn
}

// newProvisionServer creates a new provision service server to listen to rpc requests.
func newProvisionServer(l net.Listener, logger *log.Logger, dutName string, conn *grpc.ClientConn, wiringConn *grpc.ClientConn) (*grpc.Server, error) {
	s := &ProvisionServer{
		Manager:    lro.New(),
		logger:     logger,
		dutName:    dutName,
		dutClient:  api.NewDutServiceClient(conn),
		wiringConn: wiringConn,
	}
	defer s.Manager.Close()
	server := grpc.NewServer()
	api.RegisterProvisionServiceServer(server, s)
	longrunning.RegisterOperationsServer(server, s.Manager)
	logger.Println("provisionservice listen to request at ", l.Addr().String())
	return server, nil
}

// InstallCros installs a specified version of Chrome OS on the DUT, along
// with any specified DLCs.
//
// If the DUT already has the specified list of DLCs, only the missing DLCs
// will be provisioned.
func (s *ProvisionServer) InstallCros(ctx context.Context, req *api.InstallCrosRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.InstallCrosRequest: ", *req)
	op := s.Manager.NewOperation()
	cs := crosservice.NewCrOSService(s.dutName, s.dutClient, s.wiringConn, req)
	response := api.InstallCrosResponse{}
	if s.provision(ctx, &cs, op) == nil {
		response.Outcome = &api.InstallCrosResponse_Success{}
	} else {
		response.Outcome = &api.InstallCrosResponse_Failure{}
	}
	s.Manager.SetResult(op.Name, &response)
	return op, nil
}

// InstallLacros installs a specified version of Lacros on the DUT.
func (s *ProvisionServer) InstallLacros(ctx context.Context, req *api.InstallLacrosRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.InstallLacrosRequest: ", *req)
	op := s.Manager.NewOperation()
	ls, err := lacrosservice.NewLaCrOSService(s.dutName, s.dutClient, s.wiringConn, req)
	response := api.InstallLacrosResponse{}
	if err != nil {
		s.setNewOperationError(
			op,
			codes.Aborted,
			fmt.Sprintf("pre-provision: failed setup: %s", err),
			tls.ProvisionDutResponse_REASON_PROVISIONING_FAILED.String(),
		)
	} else {
		if s.provision(ctx, &ls, op) == nil {
			response.Outcome = &api.InstallLacrosResponse_Success{}
		} else {
			response.Outcome = &api.InstallLacrosResponse_Failure{
				Failure: &api.InstallFailure{
					Reason: api.InstallFailure_REASON_PROVISIONING_FAILED,
				},
			}
		}
	}
	s.Manager.SetResult(op.Name, &response)
	return op, nil
}

// InstallAsh installs a specified version of ash-chrome on the DUT.
//
// This directly overwrites the version of ash-chrome on the current root
// disk partition.
func (s *ProvisionServer) InstallAsh(ctx context.Context, req *api.InstallAshRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.InstallAshRequest: ", *req)
	op := s.Manager.NewOperation()
	cs := ashservice.NewAshService(s.dutName, s.dutClient, s.wiringConn, req)
	response := api.InstallAshResponse{}
	if s.provision(ctx, &cs, op) == nil {
		response.Outcome = &api.InstallAshResponse_Success{}
	} else {
		response.Outcome = &api.InstallAshResponse_Failure{}
	}
	s.Manager.SetResult(op.Name, &response)
	return op, nil
}

// InstallArc installs a specified version of ARC on the DUT.
//
// This directly overwrites the version of ARC on the current root
// disk partition.
func (s *ProvisionServer) InstallArc(ctx context.Context, req *api.InstallArcRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.InstallArcRequest: ", *req)
	op := s.Manager.NewOperation()
	s.Manager.SetResult(op.Name, &api.InstallArcResponse{})
	return op, nil
}

// provision effectively acts as a state transition runner for each of the
// installation services, transitioning between states as required, and
// executing each state. Operation status is also set at this state in case of
// error.
func (s *ProvisionServer) provision(ctx context.Context, si services.ServiceInterface, operation *longrunning.Operation) error {
	// Set a timeout for provisioning.
	ctx, cancel := context.WithTimeout(ctx, time.Hour)
	defer cancel()
	select {
	case <-ctx.Done():
		s.setNewOperationError(
			operation,
			codes.DeadlineExceeded,
			"provision: timed out before provisioning OS",
			tls.ProvisionDutResponse_REASON_PROVISIONING_TIMEDOUT.String())
		return fmt.Errorf("deadline failure")
	default:
	}

	for cs := si.GetFirstState(); cs != nil; cs = cs.Next() {
		if err := cs.Execute(ctx); err != nil {
			s.setNewOperationError(
				operation,
				codes.Aborted,
				fmt.Sprintf("provision: failed %s step: %s", cs.Name(), err),
				tls.ProvisionDutResponse_REASON_PROVISIONING_FAILED.String(),
			)
			return fmt.Errorf("provision step %s failure: %w", cs.Name(), err)
		}
	}

	return nil
}

// setNewOperationError is a simple helper to handle operation error propagation
func (s *ProvisionServer) setNewOperationError(op *longrunning.Operation, code codes.Code, msg, reason string) {
	status := status.New(code, msg)
	status, err := status.WithDetails(&errdetails.LocalizedMessage{
		Message: reason,
	})
	if err != nil {
		panic("Failed to set status details")
	}
	s.setError(op.Name, status)
}

// setError directly interacts with the Manager to set an error if appropriate
func (s *ProvisionServer) setError(opName string, opErr *status.Status) {
	if err := s.Manager.SetError(opName, opErr); err != nil {
		log.Printf("Failed to set Operation error, %s", err)
	}
}
