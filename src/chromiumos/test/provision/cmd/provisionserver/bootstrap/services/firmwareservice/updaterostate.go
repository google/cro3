// Copyright 2022 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// First step of FirmwareService State Machine. Installs RW firmware.
package firmwareservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"errors"
	"fmt"
	"log"
)

// FirmwareUpdateRoState updates firmware with write protection disabled.
type FirmwareUpdateRoState struct {
	service FirmwareService
}

// Execute flashes firmware with write-protection disabled using futility.
func (s FirmwareUpdateRoState) Execute(ctx context.Context) error {
	connection := s.service.GetConnectionToFlashingDevice()
	var futilityImageArgs []string

	mainRoMetadata, ok := s.service.imagesMetadata[s.service.mainRoPath.GetPath()]
	if ok {
		log.Printf("[FW Provisioning: Update RO] extracting AP image to flash\n")
		mainRoPath, err := PickAndExtractMainImage(ctx, connection, mainRoMetadata, s.service.GetBoard(), s.service.GetModel())
		if err != nil {
			return err
		}
		futilityImageArgs = append(futilityImageArgs, []string{fmt.Sprint("--image=", mainRoPath)}...)
	}

	ecRoMetadata, ok := s.service.imagesMetadata[s.service.ecRoPath.GetPath()]
	if ok {
		log.Printf("[FW Provisioning: Update RO] extracting EC image to flash\n")
		ecRoPath, err := PickAndExtractECImage(ctx, connection, ecRoMetadata, s.service.GetBoard(), s.service.GetModel())
		if err != nil {
			return err
		}
		if s.service.useServo {
			log.Printf("[FW Provisioning: Update RO] separately flashing EC over Servo with flash_ec\n")
			// futility refuses to flash EC over servod as a separate image and only
			// accepts single image: http://shortn/_dtaO92HvqW. So, for servod, we
			// use flash_ec script that to flash the EC separately.
			flashECScript, err := GetFlashECScript(ctx, connection, ecRoMetadata.archiveDir)
			if err != nil {
				return err
			}
			err = s.service.ProvisionWithFlashEC(ctx, ecRoPath, flashECScript)
			if err != nil {
				return err
			}
		} else {
			// For SSH, we can simply run `futility ... --ec-image=$EC_IMAGE ...`
			futilityImageArgs = append(futilityImageArgs, []string{fmt.Sprint("--ec_image=", ecRoPath)}...)
		}
	}

	pdRoMetadata, ok := s.service.imagesMetadata[s.service.pdRoPath.GetPath()]
	if ok {
		log.Printf("[FW Provisioning: Update RO] extracting PD image to flash\n")
		if s.service.useServo {
			return errors.New("can't flash PD as a separate image over servo")
		}
		pdRoPath, err := PickAndExtractPDImage(ctx, connection, pdRoMetadata, s.service.GetBoard(), s.service.GetModel())
		if err != nil {
			return err
		}
		futilityImageArgs = append(futilityImageArgs, []string{fmt.Sprint("--pd_image=", pdRoPath)}...)
	}

	log.Printf("[FW Provisioning: Update RO] flashing RO firmware with futility\n")
	err := s.service.FlashWithFutility(ctx, false /* WP */, futilityImageArgs)
	if err != nil {
		return err
	}

	return err
}

func (s FirmwareUpdateRoState) Next() services.ServiceState {
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
