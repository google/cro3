// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package firmwareservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"log"
)

type FirmwarePrepareState struct {
	service FirmwareService
}

// FirmwarePrepareState downloads and extracts every image from the request.
// The already downloaded images will not be downloaded and extracted again.
func (s FirmwarePrepareState) Execute(ctx context.Context) error {
	firmwareImageDestination := "DUT"
	if s.service.useServo {
		firmwareImageDestination = "ServoHost"
	}
	log.Printf("[FW Provisioning: Prepare FW] downloading Firmware Images onto %v\n", firmwareImageDestination)

	if mainRw := s.service.mainRwPath.GetPath(); len(mainRw) > 0 {
		if err := s.downloadAndProcess(ctx, mainRw); err != nil {
			return err
		}
	}
	if mainRo := s.service.mainRoPath.GetPath(); len(mainRo) > 0 {
		if err := s.downloadAndProcess(ctx, mainRo); err != nil {
			return err
		}
	}
	if ecRoPath := s.service.ecRoPath.GetPath(); len(ecRoPath) > 0 {
		if err := s.downloadAndProcess(ctx, ecRoPath); err != nil {
			return err
		}
	}
	if pdRoPath := s.service.pdRoPath.GetPath(); len(pdRoPath) > 0 {
		if err := s.downloadAndProcess(ctx, pdRoPath); err != nil {
			return err
		}
	}
	return nil
}

// downloadAndProcess downloads and extracts a provided archive,
// and stores the folder with contents in s.service.archiveFolders map.
func (s FirmwarePrepareState) downloadAndProcess(ctx context.Context, gspath string) error {
	connection := s.service.GetConnectionToFlashingDevice()
	if _, alreadyDownloaded := s.service.imagesMetadata[gspath]; !alreadyDownloaded {
		archiveMetadata, err := DownloadAndProcessArchive(ctx, connection, gspath)
		if err != nil {
			log.Printf("[FW Provisioning: Prepare FW] failed to download and process %v: %v\n", gspath, err)
			return err
		} else {
			log.Printf("[FW Provisioning: Prepare FW] downloaded %v to %v. Files in archive: %v\n",
				gspath, archiveMetadata.archivePath, len(archiveMetadata.listOfFiles))
		}
		s.service.imagesMetadata[gspath] = *archiveMetadata
	}
	return nil
}

func (s FirmwarePrepareState) Next() services.ServiceState {
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
