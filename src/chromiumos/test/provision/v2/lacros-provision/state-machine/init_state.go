// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// First step of the CrOSInit State Machine. Responsible for initialization.
package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/lacros-provision/service"
	"chromiumos/test/provision/v2/lacros-provision/state-machine/commands"
	"context"
	"fmt"
	"log"
)

// LaCrOSInitState can be thought of as the constructor state, which initializes
// variables in CrOSService
type LaCrOSInitState struct {
	service *service.LaCrOSService
}

func NewLaCrOSInitState(service *service.LaCrOSService) common_utils.ServiceState {
	return LaCrOSInitState{
		service: service,
	}
}

func (s LaCrOSInitState) Execute(ctx context.Context, log *log.Logger) error {
	log.Printf("Executing %s State:\n", s.Name())
	comms := []common_utils.CommandInterface{
		commands.NewCopyMetadataCommand(ctx, s.service),
		commands.NewGetMetadataCommand(ctx, s.service),
		commands.NewCreateImageDirectoryCommand(ctx, s.service),
		commands.NewCopyImageCommand(ctx, s.service),
		commands.NewAlignImageToPageCommand(ctx, s.service),
	}

	for _, comm := range comms {
		err := comm.Execute(log)
		if err != nil {
			return fmt.Errorf("%s, %s", comm.GetErrorMessage(), err)
		}
	}

	return nil
}

func (s LaCrOSInitState) Next() common_utils.ServiceState {
	return LaCrOSInstallState{
		service: s.service,
	}
}

func (s LaCrOSInitState) Name() string {
	return "LaCrOS Init"
}
