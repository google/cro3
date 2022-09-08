// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package state_machine

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	firmwareservice "chromiumos/test/provision/v2/fw-provision/service"
	"context"
	"log"
)

type FirmwarePrepareState struct {
	service *firmwareservice.FirmwareService
}

func NewFirmwarePrepareState(service *firmwareservice.FirmwareService) common_utils.ServiceState {
	return FirmwarePrepareState{
		service: service,
	}
}

// FirmwarePrepareState downloads and extracts every image from the request.
// The already downloaded images will not be downloaded and extracted again.
func (s FirmwarePrepareState) Execute(ctx context.Context) error {
	firmwareImageDestination := "DUT"
	if s.service.IsServoUsed() {
		firmwareImageDestination = "ServoHost"
	}
	log.Printf("[FW Provisioning: Prepare FW] downloading Firmware Images onto %v\n", firmwareImageDestination)

	if s.service.GetUseSimpleRequest() {
		imagePath, _ := s.service.GetSimpleRequest()
		if len(imagePath) > 0 {
			if err := s.service.DownloadAndProcess(ctx, imagePath); err != nil {
				return firmwareservice.UpdateFirmwareFailedErr(err.Error())
			}
		} else {
			// was checked for earlier
			panic("SimpleRequest has empty url")
		}
	} else {
		if mainRw := s.service.GetMainRwPath(); len(mainRw) > 0 {
			if err := s.service.DownloadAndProcess(ctx, mainRw); err != nil {
				return firmwareservice.UpdateFirmwareFailedErr(err.Error())
			}
		}
		if mainRo := s.service.GetMainRoPath(); len(mainRo) > 0 {
			if err := s.service.DownloadAndProcess(ctx, mainRo); err != nil {
				return firmwareservice.UpdateFirmwareFailedErr(err.Error())
			}
		}
		if ecRoPath := s.service.GetEcRoPath(); len(ecRoPath) > 0 {
			if err := s.service.DownloadAndProcess(ctx, ecRoPath); err != nil {
				return firmwareservice.UpdateFirmwareFailedErr(err.Error())
			}
		}
		if pdRoPath := s.service.GetPdRoPath(); len(pdRoPath) > 0 {
			if err := s.service.DownloadAndProcess(ctx, pdRoPath); err != nil {
				return firmwareservice.UpdateFirmwareFailedErr(err.Error())
			}
		}
	}
	return nil
}

func (s FirmwarePrepareState) Next() common_utils.ServiceState {
	if s.service.UpdateRo() {
		return FirmwareUpdateRoState(s)
	} else {
		return FirmwareUpdateRwState(s)
	}
}

const PrepareStateName = "Firmware Prepare (download/extract archives)"

func (s FirmwarePrepareState) Name() string {
	return PrepareStateName
}
