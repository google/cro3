// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Fourth and final step in the CrOSInstall State Machine. Installs DLCs
package crosservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/info"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type CrOSProvisionDLCState struct {
	service CrOSService
}

func (s CrOSProvisionDLCState) Execute(ctx context.Context) error {
	if len(s.service.dlcSpecs) == 0 {
		return nil
	}

	s.service.StopDLCService(ctx)
	defer s.service.StartDLCService(ctx)

	root, err := s.service.GetRoot(ctx)
	if err != nil {
		return fmt.Errorf("failed to get root device from DUT, %s", err)
	}
	rpn, err := s.service.GetRootPartNumber(ctx, root)
	if err != nil {
		return fmt.Errorf("failed to get root device from DUT, %s", err)
	}
	activeSlot := info.ActiveDlcMap[rpn]

	errCh := make(chan error)
	for _, spec := range s.service.dlcSpecs {
		go func(spec *api.InstallCrosRequest_DLCSpec) {
			errCh <- s.service.InstallDLC(ctx, spec, activeSlot)
		}(spec)
	}

	for range s.service.dlcSpecs {
		errTmp := <-errCh
		if errTmp == nil {
			continue
		}
		err = fmt.Errorf("%s, %s", err, errTmp)
	}
	if err != nil {
		return fmt.Errorf("failed to install the following DLCs (%s)", err)
	}

	if err := s.service.CorrectDLCPermissions(ctx); err != nil {
		return fmt.Errorf("failed to correct DLC permissions, %s", err)
	}

	return nil
}

func (s CrOSProvisionDLCState) Next() services.ServiceState {
	return CrOSInstallMiniOSState{
		service: s.service,
	}
}

func (s CrOSProvisionDLCState) Name() string {
	return "CrOS Provision DLC"
}
