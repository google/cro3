// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// First step of FirmwareService State Machine. Installs RW firmware.
package firmwareservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
	"path"
)

// FirmwareUpdateRwState updates firmware with write protection disabled.
type FirmwareUpdateRwState struct {
	service FirmwareService
}

func (s FirmwareUpdateRwState) Execute(ctx context.Context) error {
	mainRwFilename := path.Base(s.service.mainRwPath.GetPath())
	if err := s.service.CopyImageToDUT(ctx, s.service.mainRwPath, mainRwFilename); err != nil {
		return err
	}
	futilityImageArg := fmt.Sprint("--image=", s.service.GetImagePath(mainRwFilename))
	if err := s.service.ExecuteWPFutility(ctx, futilityImageArg); err != nil {
		return err
	}
	fmt.Println("Restarting to mark RW firmware update active.")
	if err := s.service.connection.Restart(ctx); err != nil {
		return err
	}
	fmt.Println("Restart successul.")
	return nil
}

func (s FirmwareUpdateRwState) Next() services.ServiceState {
	if s.service.UpdateRo() {
		return FirmwareUpdateRoState(s)
	} else {
		return FirmwareVerifyState(s)
	}
}

func (s FirmwareUpdateRwState) Name() string {
	return "Firmware Update RW"
}
