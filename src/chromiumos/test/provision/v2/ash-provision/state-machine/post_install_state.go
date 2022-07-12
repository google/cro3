// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Second step of AShPostInstall State Machine. Responsible for partition and install
package state_machine

import (
	"chromiumos/test/provision/v2/ash-provision/service"
	"chromiumos/test/provision/v2/ash-provision/state-machine/commands"
	common_utils "chromiumos/test/provision/v2/common-utils"
	"context"
	"fmt"
)

type AShPostInstallState struct {
	service *service.AShService
}

func (s AShPostInstallState) Execute(ctx context.Context) error {
	fmt.Printf("Executing %s State:\n", s.Name())
	comms := []common_utils.CommandInterface{
		commands.NewReloadBusCommand(ctx, s.service),
		commands.NewStartChromeCommand(ctx, s.service),
		commands.NewCleanUpStagingCommand(ctx, s.service),
	}

	for i, comm := range comms {
		err := comm.Execute()
		if err != nil {
			for ; i >= 0; i-- {
				if innerErr := comms[i].Revert(); innerErr != nil {
					return fmt.Errorf("failure while reverting, %s: %s", err, innerErr)
				}
			}
			return fmt.Errorf("%s, %s", comm.GetErrorMessage(), err)
		}
	}

	return nil
}

func (s AShPostInstallState) Next() common_utils.ServiceState {
	return AShPostInstallState{
		service: s.service,
	}
}

func (s AShPostInstallState) Name() string {
	return "ASh PostInstall"
}
