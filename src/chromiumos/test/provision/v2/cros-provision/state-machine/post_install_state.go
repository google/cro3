// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Third step of CrOSInstall State Machine. Responsible for stateful provisioning
package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"chromiumos/test/provision/v2/cros-provision/state-machine/commands"
	"context"
	"fmt"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/types/known/anypb"
)

type CrOSPostInstallState struct {
	service *service.CrOSService
}

func (s CrOSPostInstallState) Execute(ctx context.Context, log *log.Logger) (*anypb.Any, api.InstallResponse_Status, error) {
	log.Printf("State: Execute CrOSPostInstallState")

	comms := []common_utils.CommandInterface{
		commands.NewWaitForDutToStabilizeCommand(ctx, s.service),
		commands.NewWipeStatefulCommand(ctx, s.service),
		commands.NewStopSystemDaemonsCommand(ctx, s.service),
		commands.NewProvisionStatefulCommand(ctx, s.service),
		commands.NewClearTPMCommand(ctx, s.service),
		commands.NewRebootCommand(ctx, s.service),
		commands.NewOverwriteInstalCommand(ctx, s.service),
		commands.NewGetRootInfoCommand(ctx, s.service),
	}

	for i, comm := range comms {
		err := comm.Execute(log)
		if err != nil {
			for ; i >= 0; i-- {
				log.Printf("CrOSPostInstallState REVERT CALLED")
				if innerErr := comms[i].Revert(); innerErr != nil {
					return nil, comm.GetStatus(), fmt.Errorf("failure while reverting, %s: %s", err, innerErr)
				}
			}
			return nil, comm.GetStatus(), fmt.Errorf("%s, %s", comm.GetErrorMessage(), err)
		}
	}
	log.Printf("State: CrOSPostInstallState Completed")

	return nil, api.InstallResponse_STATUS_OK, nil
}

func (s CrOSPostInstallState) Next() common_utils.ServiceState {
	return CrOSVerifyState{
		service: s.service,
	}
}

func (s CrOSPostInstallState) Name() string {
	return "CrOS Post-Install"
}
