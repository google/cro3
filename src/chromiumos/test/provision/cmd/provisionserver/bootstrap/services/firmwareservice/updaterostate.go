// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Second step of FirmwareService State Machine. Installs RO firmware.
package firmwareservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
	"path"
)

// FirmwareUpdateRoState updates firmware with write protection disabled.
type FirmwareUpdateRoState struct {
	service FirmwareService
}

func (s FirmwareUpdateRoState) Execute(ctx context.Context) error {
	futilityImageArgs := []string{}

	if s.service.mainRoPath != nil {
		mainRoFilename := path.Base(s.service.mainRoPath.GetPath())
		if err := s.service.CopyImageToDUT(ctx, s.service.mainRoPath, mainRoFilename); err != nil {
			return err
		}
		futilityImageArgs = append(futilityImageArgs, fmt.Sprint("--image=", s.service.GetImagePath(mainRoFilename)))
	}

	if s.service.ecRoPath != nil {
		ecRoFilename := path.Base(s.service.ecRoPath.GetPath())
		if err := s.service.CopyImageToDUT(ctx, s.service.ecRoPath, ecRoFilename); err != nil {
			return err
		}
		futilityImageArgs = append(futilityImageArgs, fmt.Sprint("--ec_image=", s.service.GetImagePath(ecRoFilename)))
	}

	if s.service.pdRoPath != nil {
		pdRoFilename := path.Base(s.service.pdRoPath.GetPath())
		if err := s.service.CopyImageToDUT(ctx, s.service.pdRoPath, pdRoFilename); err != nil {
			return err
		}
		futilityImageArgs = append(futilityImageArgs, fmt.Sprint("--pd_image=", s.service.GetImagePath(pdRoFilename)))
	}

	if err := s.service.ExecuteFutility(ctx, futilityImageArgs); err != nil {
		return err
	}
	fmt.Println("Restarting to finalize RO firmware update.")
	if err := s.service.connection.Restart(ctx); err != nil {
		return err
	}
	fmt.Println("Restart successul.")
	return nil
}

func (s FirmwareUpdateRoState) Next() services.ServiceState {
	return nil
}

func (s FirmwareUpdateRoState) Name() string {
	return "Firmware Update RO"
}
