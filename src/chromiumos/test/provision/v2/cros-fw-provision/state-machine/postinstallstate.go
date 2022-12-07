// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Last step of FirmwareService State Machine.
// Cleans up temporary folders and reboots the DUT.
package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	firmwareservice "chromiumos/test/provision/v2/cros-fw-provision/service"
	"context"
	"log"

	"google.golang.org/protobuf/types/known/anypb"
)

// FirmwarePostInstallState cleans up temporary folders and reboots the DUT.
type FirmwarePostInstallState struct {
	service *firmwareservice.FirmwareService
}

// Execute deletes all folders with firmware image archives.
func (s FirmwarePostInstallState) Execute(ctx context.Context, log *log.Logger) (*anypb.Any, error) {
	s.service.DeleteArchiveDirectories()
	err := s.service.RestartDut(ctx, false)
	if err != nil {
		return nil, firmwareservice.UnreachablePostProvisionErr(err.Error())
	}

	// TODO(sfrolov): if Firmware Version Mismatched:
	// return FirmwareMismatchPostProvisionErr("expected fw version: %v, got: %v")
	return nil, nil
}

func (s FirmwarePostInstallState) Next() common_utils.ServiceState {
	return nil
}

const PostInstallStateName = "Post Install (cleanup/reboot)"

func (s FirmwarePostInstallState) Name() string {
	return PostInstallStateName
}
