// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Second step of CrOSInstall State Machine. Responsible for partition and install
package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"chromiumos/test/provision/v2/cros-provision/state-machine/commands"
	"context"
	"fmt"
	"log"
	"time"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/types/known/anypb"
)

type CrOSInstallState struct {
	service *service.CrOSService
}

func (s CrOSInstallState) Execute(ctx context.Context, log *log.Logger) (*anypb.Any, api.InstallResponse_Status, error) {
	log.Printf("State: Execute CrOSInstallState")
	comms := []common_utils.CommandInterface{
		commands.NewStopSystemDaemonsCommand(ctx, s.service),
		commands.NewInstallPartitionsCommand(ctx, s.service),
		commands.NewPostInstallCommand(ctx, s.service),
		commands.NewClearTPMCommand(ctx, s.service),
		// Install reboot may take longer, so we issue a longer timeout
		commands.NewRebootWithTimeoutCommand(500*time.Second, ctx, s.service),
	}

	for i, comm := range comms {
		err := comm.Execute(log)
		if err != nil {
			for ; i >= 0; i-- {
				log.Printf("CrOSInstallState REVERT CALLED")
				if innerErr := comms[i].Revert(); innerErr != nil {
					return nil, comm.GetStatus(), fmt.Errorf("failure while reverting, %s: %s", err, innerErr)
				}
			}
			log.Printf("- Execute CrOSInstallState failure %s\n", err)
			return nil, comm.GetStatus(), fmt.Errorf("%s, %s", comm.GetErrorMessage(), err)

		}
	}
	log.Printf("State: CrOSInstallState Completed")
	return nil, api.InstallResponse_STATUS_OK, nil
}

func (s CrOSInstallState) Next() common_utils.ServiceState {
	return CrosUpdateFirmwareState{
		service: s.service,
	}
}

func (s CrOSInstallState) Name() string {
	return "CrOS Install"
}
