// Copyright 2022 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// First step of FirmwareService State Machine. Installs RW firmware.
package firmwareservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
	"log"
)

// FirmwareUpdateRwState updates firmware with write protection disabled.
type FirmwareUpdateRwState struct {
	service FirmwareService
}

// Execute flashes firmware using futility with write-protection enabled.
func (s FirmwareUpdateRwState) Execute(ctx context.Context) error {
	connection := s.service.GetConnectionToFlashingDevice()
	mainRwMetadata := s.service.imagesMetadata[s.service.mainRwPath.GetPath()]
	log.Printf("[FW Provisioning: Update RW] extracting AP image to flash\n")
	mainRwPath, err := PickAndExtractMainImage(ctx, connection, mainRwMetadata, s.service.GetBoard(), s.service.GetModel())
	if err != nil {
		return err
	}
	futilityImageArgs := []string{fmt.Sprint("--image=", mainRwPath)}

	log.Printf("[FW Provisioning: Update RW] flashing RW firmware with futility\n")
	return s.service.FlashWithFutility(ctx, true /* WP */, futilityImageArgs)
}

func (s FirmwareUpdateRwState) Next() services.ServiceState {
	return FirmwarePostInstallState(s)
}

const UpdateRwStateName = "Firmware Update RW"

func (s FirmwareUpdateRwState) Name() string {
	return UpdateRwStateName
}
