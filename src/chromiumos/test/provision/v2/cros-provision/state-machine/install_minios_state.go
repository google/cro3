// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Sixth and final step in the CrOSInstall State Machine. Installs MiniOS
package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"chromiumos/test/provision/v2/cros-provision/state-machine/commands"
	"context"
	"fmt"
	"log"
)

type CrOSInstallMiniOSState struct {
	service *service.CrOSService
}

func (s CrOSInstallMiniOSState) Execute(ctx context.Context, log *log.Logger) error {
	log.Printf("State: Execute CrOSInstallMiniOSState")
	comms := []common_utils.CommandInterface{
		commands.NewInstallMiniOSCommand(ctx, s.service),
	}

	for i, comm := range comms {
		err := comm.Execute(log)
		if err != nil {
			for ; i >= 0; i-- {
				if innerErr := comms[i].Revert(); innerErr != nil {
					return fmt.Errorf("failure while reverting, %s: %s", err, innerErr)
				}
			}
			return fmt.Errorf("%s, %s", comm.GetErrorMessage(), err)
		}
	}
	log.Printf("State: CrOSInstallMiniOSState Completed")
	return nil
}

func (s CrOSInstallMiniOSState) Next() common_utils.ServiceState {
	return nil
}

func (s CrOSInstallMiniOSState) Name() string {
	return "CrOS Install MiniOS"
}
