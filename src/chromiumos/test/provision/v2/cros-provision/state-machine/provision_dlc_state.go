// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Fifth step in the CrOSInstall State Machine. Installs DLCs
package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"chromiumos/test/provision/v2/cros-provision/state-machine/commands"
	"context"
	"fmt"
)

type CrOSProvisionDLCState struct {
	service *service.CrOSService
}

func (s CrOSProvisionDLCState) Execute(ctx context.Context) error {
	fmt.Println("State: Execute CrOSProvisionDLCState")
	if len(s.service.DlcSpecs) == 0 {
		return nil
	}
	commands.NewStopDLCServiceCommand(ctx, s.service).Execute()
	defer commands.NewStartDLCServiceCommand(ctx, s.service).Execute()

	if err := commands.NewInstallDLCsCommand(ctx, s.service).Execute(); err != nil {
		return fmt.Errorf("failed to install the following DLCs (%s)", err)
	}

	if err := commands.NewCorrectDLCPermissionsCommand(ctx, s.service).Execute(); err != nil {
		return fmt.Errorf("failed to correct DLC permissions, %s", err)
	}

	return nil
}

func (s CrOSProvisionDLCState) Next() common_utils.ServiceState {
	return CrOSInstallMiniOSState{
		service: s.service,
	}
}

func (s CrOSProvisionDLCState) Name() string {
	return "CrOS Provision DLC"
}
