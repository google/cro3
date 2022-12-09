// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Second step of LaCrOSInstall State Machine. Responsible for partition and install
package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/lacros-provision/service"
	"chromiumos/test/provision/v2/lacros-provision/state-machine/commands"
	"context"
	"fmt"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/types/known/anypb"
)

type LaCrOSInstallState struct {
	service *service.LaCrOSService
}

func (s LaCrOSInstallState) Execute(ctx context.Context, log *log.Logger) (*anypb.Any, api.InstallResponse_Status, error) {
	log.Printf("Executing %s State:\n", s.Name())
	comms := []common_utils.CommandInterface{
		commands.NewRunVerityCommand(ctx, s.service),
		commands.NewAppendHashTreeCommand(ctx, s.service),
		commands.NewWriteManifestCommand(ctx, s.service),
		commands.NewWriteComponentManifestCommand(ctx, s.service),
		commands.NewPublishVersionCommand(ctx, s.service),
		commands.NewFixOwnershipCommand(ctx, s.service),
	}

	for i, comm := range comms {
		err := comm.Execute(log)
		if err != nil {
			for ; i >= 0; i-- {
				if innerErr := comms[i].Revert(); innerErr != nil {
					return nil, comm.GetStatus(), fmt.Errorf("failure while reverting, %s: %s", err, innerErr)
				}
			}
			return nil, comm.GetStatus(), fmt.Errorf("%s, %s", comm.GetErrorMessage(), err)
		}
	}

	return nil, api.InstallResponse_STATUS_OK, nil
}

func (s LaCrOSInstallState) Next() common_utils.ServiceState {
	return LaCrOSVerifyState{
		service: s.service,
	}
}

func (s LaCrOSInstallState) Name() string {
	return "LaCrOS Install"
}
