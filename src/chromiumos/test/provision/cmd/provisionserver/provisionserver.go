// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Implements provision_service.proto (see proto for details)
package provisionserver

import (
	"context"

	"go.chromium.org/chromiumos/config/go/longrunning"
	"go.chromium.org/chromiumos/config/go/test/api"
)

// InstallCros installs a specified version of Chrome OS on the DUT, along
// with any specified DLCs.
//
// If the DUT already has the specified list of DLCs, only the missing DLCs
// will be provisioned.
func (s *provision) InstallCros(ctx context.Context, req *api.InstallCrosRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.InstallCrosRequest: ", *req)
	op := s.manager.NewOperation()
	response := api.InstallCrosResponse{}
	if fr, err := s.installCros(ctx, req, op); err != nil {
		response.Outcome = &api.InstallCrosResponse_Failure{
			Failure: fr,
		}
	} else {
		response.Outcome = &api.InstallCrosResponse_Success{}
	}
	s.manager.SetResult(op.Name, &response)
	return op, nil
}

// InstallLacros installs a specified version of Lacros on the DUT.
func (s *provision) InstallLacros(ctx context.Context, req *api.InstallLacrosRequest) (*longrunning.Operation, error) {
	op := s.manager.NewOperation()
	response := api.InstallLacrosResponse{}
	if fr, err := s.installLacros(ctx, req, op); err != nil {
		response.Outcome = &api.InstallLacrosResponse_Failure{
			Failure: fr,
		}
	} else {
		response.Outcome = &api.InstallLacrosResponse_Success{}
	}
	s.manager.SetResult(op.Name, &response)
	return op, nil
}

// InstallAsh installs a specified version of ash-chrome on the DUT.
//
// This directly overwrites the version of ash-chrome on the current root
// disk partition.
func (s *provision) InstallAsh(ctx context.Context, req *api.InstallAshRequest) (*longrunning.Operation, error) {
	op := s.manager.NewOperation()
	response := api.InstallAshResponse{}
	if fr, err := s.installAsh(ctx, req, op); err != nil {
		response.Outcome = &api.InstallAshResponse_Failure{
			Failure: fr,
		}
	} else {
		response.Outcome = &api.InstallAshResponse_Success{}
	}
	s.manager.SetResult(op.Name, &response)
	return op, nil
}

// InstallArc installs a specified version of ARC on the DUT.
//
// This directly overwrites the version of ARC on the current root
// disk partition.
func (s *provision) InstallArc(ctx context.Context, req *api.InstallArcRequest) (*longrunning.Operation, error) {
	op := s.manager.NewOperation()
	response := api.InstallArcResponse{}
	if fr, err := s.installArc(ctx, req, op); err != nil {
		response.Outcome = &api.InstallArcResponse_Failure{
			Failure: fr,
		}
	} else {
		response.Outcome = &api.InstallArcResponse_Success{}
	}
	s.manager.SetResult(op.Name, &response)
	return op, nil
}

// InstallFirmware installs AP/EC firmware to the DUT
func (s *provision) InstallFirmware(ctx context.Context, req *api.InstallFirmwareRequest) (*longrunning.Operation, error) {
	s.logger.Println("Received api.InstallFirmwareRequest: ", *req)
	op := s.manager.NewOperation()
	response := api.InstallFirmwareResponse{}
	if fr, err := s.installFirmware(ctx, req, op); err != nil {
		response.Outcome = &api.InstallFirmwareResponse_Failure{
			Failure: fr,
		}
	} else {
		response.Outcome = &api.InstallFirmwareResponse_Success{}
	}
	s.manager.SetResult(op.Name, &response)
	return op, nil
}
