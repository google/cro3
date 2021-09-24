// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Second step of CrOSInstall State Machine. Responsible for stateful provisioning
package crosservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
)

type CrOSPostInstallState struct {
	service CrOSService
}

func (s CrOSPostInstallState) Execute(ctx context.Context) error {
	if !s.service.preserverStateful {
		if err := s.service.WipeStateful(ctx); err != nil {
			return fmt.Errorf("failed to wipe stateful, %s", err)
		}

		if err := s.service.connection.Restart(ctx); err != nil {
			return fmt.Errorf("failed to restart dut, %s", err)
		}
	}

	if err := s.service.ProvisionStateful(ctx); err != nil {
		return fmt.Errorf("failed to provision stateful, %s", err)
	}

	if err := s.service.OverwiteInstall(ctx); err != nil {
		return fmt.Errorf("failed to overwite install, %s", err)
	}

	if err := s.service.connection.Restart(ctx); err != nil {
		return fmt.Errorf("failed to restart dut, %s", err)
	}

	return nil
}

func (s CrOSPostInstallState) Next() services.ServiceState {
	return CrOSVerifyState{
		service: s.service,
	}
}

func (s CrOSPostInstallState) Name() string {
	return "CrOS Post-Install"
}
