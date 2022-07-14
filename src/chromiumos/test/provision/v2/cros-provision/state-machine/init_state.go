// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// First step of the CrOSInstall State Machine. Responsible for initialization.
package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"chromiumos/test/provision/v2/cros-provision/state-machine/commands"
	"context"
	"fmt"
)

// CrosInitState can be thought of as the constructor state, which initializes
// variables in CrOSService
type CrOSInitState struct {
	service *service.CrOSService
}

func NewCrOSInitState(service *service.CrOSService) common_utils.ServiceState {
	return CrOSInitState{
		service: service,
	}
}

func (s CrOSInitState) Execute(ctx context.Context) error {
	fmt.Println("State: Execute CrOSInitState")
	comms := []common_utils.CommandInterface{
		commands.NewCreateProvisionMarkerCommand(ctx, s.service),
		commands.NewGetRootInfoCommand(ctx, s.service),
		commands.NewGetBoardCommand(ctx, s.service),
	}

	for _, comm := range comms {
		err := comm.Execute()
		if err != nil {
			return fmt.Errorf("%s, %s", comm.GetErrorMessage(), err)
		}
	}

	return nil
}

func (s CrOSInitState) Next() common_utils.ServiceState {
	return CrOSInstallState{
		service: s.service,
	}
}

func (s CrOSInitState) Name() string {
	return "CrOS Init"
}
