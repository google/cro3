// Copyright 2022 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Last step of FirmwareService State Machine.
// Cleans up temporary folders and reboots the DUT.
package firmwareservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
)

// FirmwarePostInstallState cleans up temporary folders and reboots the DUT.
type FirmwarePostInstallState struct {
	service FirmwareService
}

// Execute deletes all folders with firmware image archives.
func (s FirmwarePostInstallState) Execute(ctx context.Context) error {
	s.service.deleteArchiveDirectories()
	return s.service.RestartDut(ctx, false)
}

func (s FirmwarePostInstallState) Next() services.ServiceState {
	return nil
}

const PostInstallStateName = "Post Install (cleanup/reboot)"

func (s FirmwarePostInstallState) Name() string {
	return PostInstallStateName
}
