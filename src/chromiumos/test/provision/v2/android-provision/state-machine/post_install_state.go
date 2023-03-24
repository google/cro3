// Copyright 2023 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package state_machine

import (
	"context"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
	"google.golang.org/protobuf/types/known/anypb"

	"chromiumos/test/provision/v2/android-provision/common"
	"chromiumos/test/provision/v2/android-provision/service"
	"chromiumos/test/provision/v2/android-provision/state-machine/commands"
	common_utils "chromiumos/test/provision/v2/common-utils"
)

type PostInstallState struct {
	svc *service.AndroidService
}

func (s PostInstallState) Execute(ctx context.Context, log *log.Logger) (*anypb.Any, api.InstallResponse_Status, error) {
	log.Println("State: Execute AndroidPostInstallState")
	ctx = context.WithValue(ctx, "stage", common.PostInstall)
	cmds := []common_utils.CommandInterface{
		commands.NewCleanupCommand(ctx, s.svc),
	}
	for _, c := range cmds {
		// Ignore errors. Don't fail provisioning due to cleanup errors.
		c.Execute(log)
	}
	log.Println("State: AndroidPostInstallState Completed")
	// Return metadata with provisioned OS and packages.
	resp, _ := s.svc.MarshalResponseMetadata()
	return resp, api.InstallResponse_STATUS_OK, nil
}

func (s PostInstallState) Next() common_utils.ServiceState {
	return nil
}

func (s PostInstallState) Name() string {
	return "Android Post Install State"
}
