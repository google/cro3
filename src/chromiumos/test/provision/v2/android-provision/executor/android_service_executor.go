// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package executor

import (
	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"

	"chromiumos/test/provision/v2/android-provision/service"
	state_machine "chromiumos/test/provision/v2/android-provision/state-machine"
	common_utils "chromiumos/test/provision/v2/common-utils"
)

type AndroidProvisionExecutor struct {
}

func (c *AndroidProvisionExecutor) GetFirstState(dut *lab_api.Dut, dutClient api.DutServiceClient, req *api.InstallRequest) (common_utils.ServiceState, error) {
	svc, err := service.NewAndroidService(dut, dutClient, req)
	if err != nil {
		return nil, err
	}
	return state_machine.NewPrepareState(svc), nil
}
