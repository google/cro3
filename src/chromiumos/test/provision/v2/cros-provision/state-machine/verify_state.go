// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Fourth step in the CrOSInstall State Machine. Currently a noop, to be implemented
package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
)

type CrOSVerifyState struct {
	service *service.CrOSService
}

func (s CrOSVerifyState) Execute(ctx context.Context) error {
	// Currently there is no verification post step as we don't specify install type
	return nil
}

func (s CrOSVerifyState) Next() common_utils.ServiceState {
	return CrOSProvisionDLCState{
		service: s.service,
	}
}

func (s CrOSVerifyState) Name() string {
	return "CrOS Verify"
}
