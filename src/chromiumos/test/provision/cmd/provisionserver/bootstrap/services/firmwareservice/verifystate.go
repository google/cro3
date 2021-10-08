// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Final step of FirmwareService State Machine. Currently a noop, to be implemented
package firmwareservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
)

type FirmwareVerifyState struct {
	service FirmwareService
}

func (s FirmwareVerifyState) Execute(ctx context.Context) error {
	// TODO(sfrolov): consider verifying signatures here.
	return nil
}

func (s FirmwareVerifyState) Next() services.ServiceState {
	return nil
}

func (s FirmwareVerifyState) Name() string {
	return "Firmware Verify"
}
