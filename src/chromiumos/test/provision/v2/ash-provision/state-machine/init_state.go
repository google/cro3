// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// First step of the CrOSInit State Machine. Responsible for initialization.
package state_machine

import (
	"chromiumos/test/provision/v2/ash-provision/service"
	"chromiumos/test/provision/v2/ash-provision/state-machine/commands"
	common_utils "chromiumos/test/provision/v2/common-utils"
	"context"
	"fmt"
)

// AShInitState can be thought of as the constructor state, which initializes
// variables in CrOSService
type AShInitState struct {
	service *service.AShService
}

func NewAShInitState(service *service.AShService) common_utils.ServiceState {
	return AShInitState{
		service: service,
	}
}

func (s AShInitState) Execute(ctx context.Context) error {
	fmt.Printf("Executing %s State:\n", s.Name())
	comms := []common_utils.CommandInterface{
		commands.NewCleanUpStagingCommand(ctx, s.service),
		commands.NewCreateNewStagingDirsCommand(ctx, s.service),
		commands.NewCopyImageCommand(ctx, s.service),
		commands.NewCreateBinaryDirsCommand(ctx, s.service),
		commands.NewStopChromeCommand(ctx, s.service),
		commands.NewKillChromeCommand(ctx, s.service),
	}

	for _, comm := range comms {
		err := comm.Execute()
		if err != nil {
			return fmt.Errorf("%s, %s", comm.GetErrorMessage(), err)
		}
	}

	return nil
}

func (s AShInitState) Next() common_utils.ServiceState {
	return AShInstallState{
		service: s.service,
	}
}

func (s AShInitState) Name() string {
	return "ASh Init"
}
