// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements provision_service.proto (see proto for details)
package provisionserver

import (
	"context"
	"fmt"
	"log"
	"time"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
	"go.chromium.org/luci/common/errors"
	"google.golang.org/genproto/googleapis/rpc/errdetails"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"chromiumos/lro"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/ashservice"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/crosservice"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/firmwareservice"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services/lacrosservice"
)

// provision holds info for provisioning.
type provision struct {
	logger    *log.Logger
	dut       *lab_api.Dut
	dutClient api.DutServiceClient
	// Used only for server implementation.
	manager *lro.Manager
	// Used only for flashing firmware.
	servoClient api.ServodServiceClient
}

// newProvision creates new provision to perform.
func NewProvision(logger *log.Logger, dut *lab_api.Dut, dutServiceAddr string) (*provision, func(), error) {
	var conns []*grpc.ClientConn
	closer := func() {
		for _, conn := range conns {
			conn.Close()
		}
		conns = nil
	}
	dutConn, err := grpc.Dial(dutServiceAddr, grpc.WithInsecure())
	if err != nil {
		return nil, closer, errors.Annotate(err, "new provision: failed to connect to dut-service").Err()
	}
	conns = append(conns, dutConn)

	var servoClient api.ServodServiceClient
	if servoConf := dut.GetChromeos().GetServo(); servoConf != nil {
		servoAddr := fmt.Sprintf("%s:%d", servoConf.GetServodAddress().GetAddress(), servoConf.GetServodAddress().GetPort())
		servoConn, err := grpc.Dial(servoAddr, grpc.WithInsecure())
		if err != nil {
			return nil, closer, errors.Annotate(err, "new provision: failed to connect to cros-servod").Err()
		}
		conns = append(conns, servoConn)
		servoClient = api.NewServodServiceClient(servoConn)
	}

	return &provision{
		logger:      logger,
		dut:         dut,
		dutClient:   api.NewDutServiceClient(dutConn),
		servoClient: servoClient,
	}, closer, nil
}

// newProvision creates new provision to perform.
func NewProvisionFromExistingDutClient(logger *log.Logger, dut *lab_api.Dut, dutClient api.DutServiceClient) (*provision, error) {
	return &provision{
		logger:    logger,
		dut:       dut,
		dutClient: dutClient,
	}, nil
}

// installState installs all required software from ProvisionState.
func (s *provision) installState(ctx context.Context, state *api.ProvisionState, op *longrunning.Operation) (*api.InstallFailure, error) {
	s.logger.Println("Start provison...")
	if si := state.GetSystemImage(); si != nil {
		var dlcSpecs []*api.InstallCrosRequest_DLCSpec
		for _, id := range state.GetSystemImage().GetDlcs() {
			dlcSpec := &api.InstallCrosRequest_DLCSpec{
				Id: id.Value,
			}
			dlcSpecs = append(dlcSpecs, dlcSpec)
		}
		if fr, err := s.installCros(ctx, &api.InstallCrosRequest{
			CrosImagePath:    state.GetSystemImage().GetSystemImagePath(),
			DlcSpecs:         dlcSpecs,
			PreserveStateful: false,
			PreventReboot:    state.GetPreventReboot(),
		}, op); err != nil {
			return fr, err
		}
	}
	for _, pkg := range state.GetPackages() {
		packageName := pkg.GetPortagePackage().GetPackageName()
		s.logger.Printf("Running package: %s, category: %s, version: %s", packageName, pkg.GetPortagePackage().GetCategory(), pkg.GetPortagePackage().GetVersion())
		switch packageName {
		case "chromeos-lacros":
			if fr, err := s.installLacros(ctx, &api.InstallLacrosRequest{
				LacrosImagePath: pkg.PackagePath,
			}, op); err != nil {
				return fr, err
			}
		case "chromeos-chrome":
			if fr, err := s.installAsh(ctx, &api.InstallAshRequest{
				AshImagePath: pkg.PackagePath,
			}, op); err != nil {
				return fr, err
			}
		default:
			fr := &api.InstallFailure{
				Reason: api.InstallFailure_REASON_PROVISIONING_FAILED,
			}
			s.setNewOperationError(
				op,
				codes.DeadlineExceeded,
				"provision: timed out before provisioning OS",
				fr.Reason.String())
			return fr, fmt.Errorf("provision: unsupported package %s", packageName)
		}
		s.logger.Printf("Received package: %s", pkg)
	}
	if fw := state.GetFirmware(); fw != nil {
		if fr, err := s.installFirmware(ctx, &api.InstallFirmwareRequest{
			FirmwareConfig: fw,
			UseServo:       state.UseServo,
			Force:          state.FirmwareForce,
		}, nil); err != nil {
			return fr, err
		}
	}
	return nil, nil
}

// installCros installs a specified version of Chrome OS on the DUT, along
// with any specified DLCs.
func (s *provision) installCros(ctx context.Context, req *api.InstallCrosRequest, op *longrunning.Operation) (*api.InstallFailure, error) {
	s.logger.Println("Received api.InstallCrosRequest: ", req)
	cs := crosservice.NewCrOSService(s.dut, s.dutClient, req)
	return s.execute(ctx, &cs, op)
}

// installLacros installs a specified version of Lacros on the DUT.
func (s *provision) installLacros(ctx context.Context, req *api.InstallLacrosRequest, op *longrunning.Operation) (*api.InstallFailure, error) {
	s.logger.Println("Received api.InstallLacrosRequest: ", req)
	ls, err := lacrosservice.NewLaCrOSService(s.dut, s.dutClient, req)
	if err != nil {
		fr := &api.InstallFailure{
			Reason: api.InstallFailure_REASON_PROVISIONING_FAILED,
		}
		s.setNewOperationError(
			op,
			codes.Aborted,
			fmt.Sprintf("pre-provision: failed setup: %s", err),
			fr.Reason.String(),
		)
		return fr, err
	}
	return s.execute(ctx, &ls, op)
}

// installAsh installs a specified version of ash-chrome on the DUT.
func (s *provision) installAsh(ctx context.Context, req *api.InstallAshRequest, op *longrunning.Operation) (*api.InstallFailure, error) {
	s.logger.Println("Received api.InstallAshRequest: ", req)
	cs := ashservice.NewAshService(s.dut, s.dutClient, req)
	return s.execute(ctx, &cs, op)
}

// installArc installs a specified version of ARC on the DUT.
//
// TODO(shapiroc): Implement this
func (s *provision) installArc(ctx context.Context, req *api.InstallArcRequest, op *longrunning.Operation) (*api.InstallFailure, error) {
	s.logger.Println("Received api.InstallArcRequest: ", req)
	return &api.InstallFailure{
		Reason: api.InstallFailure_REASON_PROVISIONING_FAILED,
	}, fmt.Errorf("not implemented")
}

// installFirmware installs requested firmware to the DUT.
func (s *provision) installFirmware(ctx context.Context, req *api.InstallFirmwareRequest, op *longrunning.Operation) (*api.InstallFailure, error) {
	s.logger.Println("Received api.InstallFirmwareRequest: ", req)
	ls, err := firmwareservice.NewFirmwareService(ctx, s.dut, s.dutClient, s.servoClient, req)
	if err != nil {
		fr := &api.InstallFailure{
			Reason: api.InstallFailure_REASON_PROVISIONING_FAILED,
		}
		s.setNewOperationError(
			op,
			codes.Aborted,
			fmt.Sprintf("pre-provision: failed setup: %s", err),
			fr.Reason.String(),
		)
		return fr, err
	}
	return s.execute(ctx, ls, op)
}

// execute effectively acts as a state transition runner for each of the
// installation services, transitioning between states as required, and
// executing each state. Operation status is also set at this state in case of
// error.
func (s *provision) execute(ctx context.Context, si services.ServiceInterface, op *longrunning.Operation) (*api.InstallFailure, error) {
	// Set a timeout for provisioning.
	ctx, cancel := context.WithTimeout(ctx, time.Hour)
	defer cancel()
	select {
	case <-ctx.Done():
		fr := &api.InstallFailure{
			Reason: api.InstallFailure_REASON_PROVISIONING_TIMEDOUT,
		}
		s.setNewOperationError(
			op,
			codes.DeadlineExceeded,
			"provision: timed out before provisioning OS",
			fr.Reason.String())
		return fr, fmt.Errorf("deadline failure")
	default:
	}

	// states list keeps the executed and failed ServiceStates,
	// so that they can be undone/cleaned up upon failure.
	var states []services.ServiceState

	for cs := si.GetFirstState(); cs != nil; cs = cs.Next() {
		states = append(states, cs)
		if err := cs.Execute(ctx); err != nil {
			if cleanupErr := si.CleanupOnFailure(states, err); cleanupErr != nil {
				s.logger.Println("CleanupOnFailure failed:", cleanupErr.Error())
			}
			fr := &api.InstallFailure{
				Reason: api.InstallFailure_REASON_PROVISIONING_FAILED,
			}
			s.setNewOperationError(
				op,
				codes.Aborted,
				fmt.Sprintf("provision: failed %s step: %s", cs.Name(), err),
				fr.Reason.String())
			return fr, fmt.Errorf("provision step %s failure: %w", cs.Name(), err)
		}
	}
	return nil, nil
}

// setNewOperationError is a simple helper to handle operation error propagation
func (s *provision) setNewOperationError(op *longrunning.Operation, code codes.Code, msg, reason string) {
	if op == nil || s.manager == nil {
		// Skipping if no operation or manager provided.
		return
	}
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
func (s *provision) setError(opName string, opErr *status.Status) {
	if err := s.manager.SetError(opName, opErr); err != nil {
		log.Printf("Failed to set Operation error, %s", err)
	}
}
