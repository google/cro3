// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Executor defines a state initializer for each state. Usable by server to start.
// Under normal conditions this would be part of service, but go being go, it
// would create an impossible cycle
package server

import (
	common_utils "chromiumos/test/provision/v2/common-utils"

	"go.chromium.org/chromiumos/config/go/test/api"
	lab_api "go.chromium.org/chromiumos/config/go/test/lab/api"
)

type ProvisionExecutor interface {
	GetFirstState(dut *lab_api.Dut, dutClient api.DutServiceClient, req *api.InstallRequest) (common_utils.ServiceState, error)
}
