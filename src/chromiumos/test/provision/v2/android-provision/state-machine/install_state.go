// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Package state_machine defines initial steps of the AndroidInstall State Machine.
package state_machine

import (
	"context"
	"fmt"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
	"go.chromium.org/luci/common/errors"
	"google.golang.org/protobuf/types/known/anypb"

	"chromiumos/test/provision/v2/android-provision/service"
	"chromiumos/test/provision/v2/android-provision/state-machine/commands"
	common_utils "chromiumos/test/provision/v2/common-utils"
)

type InstallState struct {
	svc *service.AndroidService
}

func (s InstallState) Execute(ctx context.Context, log *log.Logger) (*anypb.Any, api.InstallResponse_Status, error) {
	log.Println("State: Execute AndroidPrepareState")
	cmds := []common_utils.CommandInterface{
		commands.NewCopyAPKCommand(ctx, s.svc),
		commands.NewInstallAPKCommand(ctx, s.svc),
		commands.NewRestartAppCommand(ctx, s.svc),
	}
	for i, c := range cmds {
		if err := c.Execute(log); err != nil {
			log.Printf("State: Execute AndroidInstallState failure %s\n", err)
			log.Println("State: Revert AndroidInstallState")
			for ; i >= 0; i-- {
				if e := cmds[i].Revert(); e != nil {
					err = errors.Annotate(err, "failure while reverting %s", e).Err()
					break
				}
			}
			resp, _ := s.svc.MarshalResponseMetadata()
			return resp, c.GetStatus(), fmt.Errorf("%s: %s", c.GetErrorMessage(), err)
		}
	}
	log.Println("State: AndroidInstallState Completed")
	return nil, api.InstallResponse_STATUS_OK, nil
}

func (s InstallState) Next() common_utils.ServiceState {
	return CleanupState{
		svc: s.svc,
	}
}

func (s InstallState) Name() string {
	return "Android Install State"
}
