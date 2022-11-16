// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package state_machine defines initial steps of the AndroidInstall State Machine.
package state_machine

import (
	"context"
	"fmt"
	"log"

	"chromiumos/test/provision/v2/android-provision/service"
	"chromiumos/test/provision/v2/android-provision/state-machine/commands"
	common_utils "chromiumos/test/provision/v2/common-utils"
)

type InstallState struct {
	svc *service.AndroidService
}

func (s InstallState) Execute(ctx context.Context, log *log.Logger) error {
	log.Printf("%s: begin Execute", s.Name())
	cmds := []common_utils.CommandInterface{
		commands.NewCopyAPKCommand(ctx, s.svc),
		commands.NewInstallAPKCommand(ctx, s.svc),
	}
	for _, c := range cmds {
		if err := c.Execute(log); err != nil {
			return fmt.Errorf("%s: %s", c.GetErrorMessage(), err)
		}
	}
	return nil
}

func (s InstallState) Next() common_utils.ServiceState {
	return CleanupState{
		svc: s.svc,
	}
}

func (s InstallState) Name() string {
	return "Android Install State"
}
