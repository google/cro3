// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// First step of FirmwareService State Machine. Installs RW firmware.
package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	firmwareservice "chromiumos/test/provision/v2/fw-provision/service"
	"context"
	"fmt"
	"log"
)

// FirmwareUpdateRoState updates firmware with write protection disabled.
type FirmwareUpdateRoState struct {
	service *firmwareservice.FirmwareService
}

// Execute flashes firmware with write-protection disabled using futility.
func (s FirmwareUpdateRoState) Execute(ctx context.Context) error {
	connection := s.service.GetConnectionToFlashingDevice()

	// form futility command args based on the request
	var futilityImageArgs []string
	if s.service.GetUseSimpleRequest() {
		// Simple Request
		imagePath, flashRo := s.service.GetSimpleRequest()
		if !flashRo {
			panic("entered FirmwareUpdateRoState when flashRo == false") // impossible
		}
		imgMetadata, ok := s.service.GetImageMetadata(imagePath)
		if !ok {
			panic("no metadata for SimpleRequest") // impossible
		}
		futilityImageArgs = append(futilityImageArgs, []string{fmt.Sprint("--archive=", imgMetadata.ArchivePath)}...)
	} else {
		// Detailed Request
		mainRoMetadata, ok := s.service.GetImageMetadata(s.service.GetMainRoPath())
		if ok {
			log.Printf("[FW Provisioning: Update RO] extracting AP image to flash\n")
			mainRoPath, err := firmwareservice.PickAndExtractMainImage(ctx, connection, mainRoMetadata, s.service.GetBoard(), s.service.GetModel())
			if err != nil {
				return firmwareservice.UpdateFirmwareFailedErr(err.Error())
			}
			futilityImageArgs = append(futilityImageArgs, []string{fmt.Sprint("--image=", mainRoPath)}...)
		}

		ecRoMetadata, ok := s.service.GetImageMetadata(s.service.GetEcRoPath())
		if ok {
			log.Printf("[FW Provisioning: Update RO] extracting EC image to flash\n")
			ecRoPath, err := firmwareservice.PickAndExtractECImage(ctx, connection, ecRoMetadata, s.service.GetBoard(), s.service.GetModel())
			if err != nil {
				return firmwareservice.UpdateFirmwareFailedErr(err.Error())
			}
			if s.service.IsServoUsed() {
				log.Printf("[FW Provisioning: Update RO] separately flashing EC over Servo with flash_ec\n")
				// futility refuses to flash EC over servod as a separate image and only
				// accepts single image: http://shortn/_dtaO92HvqW. So, for servod, we
				// use flash_ec script that to flash the EC separately.
				flashECScript, err := firmwareservice.GetFlashECScript(ctx, connection, ecRoMetadata.ArchiveDir)
				if err != nil {
					return firmwareservice.UpdateFirmwareFailedErr(err.Error())
				}
				err = s.service.ProvisionWithFlashEC(ctx, ecRoPath, flashECScript)
				if err != nil {
					return firmwareservice.UpdateFirmwareFailedErr(err.Error())
				}
			} else {
				// For SSH, we can simply run `futility ... --ec-image=$EC_IMAGE ...`
				futilityImageArgs = append(futilityImageArgs, []string{fmt.Sprint("--ec_image=", ecRoPath)}...)
			}
		}

		pdRoMetadata, ok := s.service.GetImageMetadata(s.service.GetPdRoPath())
		if ok {
			log.Printf("[FW Provisioning: Update RO] extracting PD image to flash\n")
			if s.service.IsServoUsed() {
				return firmwareservice.UpdateFirmwareFailedErr("can't flash PD as a separate image over servo")
			}
			pdRoPath, err := firmwareservice.PickAndExtractPDImage(ctx, connection, pdRoMetadata, s.service.GetBoard(), s.service.GetModel())
			if err != nil {
				return firmwareservice.UpdateFirmwareFailedErr(err.Error())
			}
			futilityImageArgs = append(futilityImageArgs, []string{fmt.Sprint("--pd_image=", pdRoPath)}...)
		}
	}

	log.Printf("[FW Provisioning: Update RO] flashing RO firmware with futility\n")
	err := s.service.FlashWithFutility(ctx, false /* WP */, futilityImageArgs)
	if err != nil {
		return firmwareservice.UpdateFirmwareFailedErr(err.Error())
	}

	return nil
}

func (s FirmwareUpdateRoState) Next() common_utils.ServiceState {
	if s.service.UpdateRw() {
		return FirmwareUpdateRwState(s)
	} else {
		return FirmwarePostInstallState(s)
	}
}

const UpdateRoStateName = "Firmware Update RO"

func (s FirmwareUpdateRoState) Name() string {
	return UpdateRoStateName
}
