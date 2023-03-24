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

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/service"
	"chromiumos/test/provision/v2/android-provision/state-machine/commands"
	common_utils "chromiumos/test/provision/v2/common-utils"
)

type PackageInstallState struct {
	svc *service.AndroidService
}

func (s PackageInstallState) Execute(ctx context.Context, log *log.Logger) (*anypb.Any, api.InstallResponse_Status, error) {
	log.Println("State: Execute AndroidPackageInstallState")
	ctx = context.WithValue(ctx, "stage", common.PackageInstall)
	cmds := []common_utils.CommandInterface{
		commands.NewInstallAPKCommand(ctx, s.svc),
		commands.NewRestartAppCommand(ctx, s.svc),
		commands.NewCleanupCommand(ctx, s.svc),
	}
	for i, c := range cmds {
		if err := c.Execute(log); err != nil {
			log.Printf("State: Execute AndroidPackageInstallState failure %s\n", err)
			log.Println("State: Revert AndroidPackageInstallState")
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
	log.Println("State: AndroidPackageInstallState Completed")
	return nil, api.InstallResponse_STATUS_OK, nil
}

func (s PackageInstallState) Next() common_utils.ServiceState {
	return PostInstallState{
		svc: s.svc,
	}
}

func (s PackageInstallState) Name() string {
	return "Android Package Install State"
}
