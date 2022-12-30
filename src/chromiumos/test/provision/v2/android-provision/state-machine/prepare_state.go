// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

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

type PrepareState struct {
	svc *service.AndroidService
}

func NewPrepareState(s *service.AndroidService) common_utils.ServiceState {
	return PrepareState{
		svc: s,
	}
}

func (s PrepareState) Execute(ctx context.Context, log *log.Logger) (*anypb.Any, api.InstallResponse_Status, error) {
	log.Println("State: Execute AndroidPrepareState")
	cmds := []common_utils.CommandInterface{
		commands.NewResolveCIPDPackageCommand(ctx, s.svc),
		commands.NewRestartADBCommand(ctx, s.svc),
		commands.NewGetInstalledPackageVersionCommand(ctx, s.svc),
		commands.NewFetchCIPDPackageCommand(ctx, s.svc),
		commands.NewExtractAPKFileCommand(ctx, s.svc),
		commands.NewUploadAPKToGSCommand(ctx, s.svc),
	}
	for i, c := range cmds {
		if err := c.Execute(log); err != nil {
			log.Printf("State: Execute AndroidPrepareState failure %s\n", err)
			log.Println("State: Revert AndroidPrepareState")
			for ; i >= 0; i-- {
				if e := cmds[i].Revert(); e != nil {
					err = errors.Annotate(err, "failure while reverting %s", e).Err()
					break
				}
			}
			return nil, c.GetStatus(), fmt.Errorf("%s: %s", c.GetErrorMessage(), err)
		}
	}
	log.Println("State: AndroidPrepareState Completed")
	return nil, api.InstallResponse_STATUS_OK, nil
}

func (s PrepareState) Next() common_utils.ServiceState {
	return InstallState{
		svc: s.svc,
	}
}

func (s PrepareState) Name() string {
	return "Android Prepare State"
}
