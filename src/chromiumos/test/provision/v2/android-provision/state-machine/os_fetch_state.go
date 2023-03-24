// Copyright 2023 The ChromiumOS Authors
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

type OSFetchState struct {
	svc *service.AndroidService
}

func (s OSFetchState) Execute(ctx context.Context, log *log.Logger) (*anypb.Any, api.InstallResponse_Status, error) {
	log.Println("State: Execute AndroidOSFetchState")
	ctx = context.WithValue(ctx, "stage", common.OSFetch)
	cmds := []common_utils.CommandInterface{
		// TODO(b:274782508): Add the new copy command after refactoring copy_apk_command
		commands.NewExtractZipCommand(ctx, s.svc),
	}
	for i, c := range cmds {
		if err := c.Execute(log); err != nil {
			log.Printf("State: Execute AndroidOSFetchState failure %s\n", err)
			log.Println("State: Revert AndroidOSFetchState")
			for ; i >= 0; i-- {
				if e := cmds[i].Revert(); e != nil {
					err = errors.Annotate(err, "failure while reverting %s", e).Err()
					break
				}
			}
			return nil, c.GetStatus(), fmt.Errorf("%s: %s", c.GetErrorMessage(), err)
		}
	}
	log.Println("State: AndroidOSFetchState Completed")
	return nil, api.InstallResponse_STATUS_OK, nil
}

func (s OSFetchState) Next() common_utils.ServiceState {
	return OSInstallState{
		svc: s.svc,
	}
}

func (s OSFetchState) Name() string {
	return "Android OS Fetch State"
}
