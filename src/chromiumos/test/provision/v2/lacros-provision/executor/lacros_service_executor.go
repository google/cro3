// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package executor

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/lacros-provision/service"

	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"

	state_machine "chromiumos/test/provision/v2/lacros-provision/state-machine"
)

type LaCrOSProvisionExecutor struct {
}

func (c *LaCrOSProvisionExecutor) GetFirstState(dut *lab_api.Dut, dutClient api.DutServiceClient, req *api.InstallRequest) (common_utils.ServiceState, error) {
	cs, err := service.NewLaCrOSService(dut, dutClient, req)
	if err != nil {
		return nil, err
	}
	return state_machine.NewLaCrOSInitState(*cs), nil
}
