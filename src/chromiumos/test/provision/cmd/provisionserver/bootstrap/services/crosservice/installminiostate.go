// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Fourth and final step in the CrOSInstall State Machine. Installs DLCs
package crosservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/info"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
	"log"
)

type CrOSInstallMiniOSState struct {
	service CrOSService
}

func (s CrOSInstallMiniOSState) Execute(ctx context.Context) error {

	root, err := s.service.GetRoot(ctx)
	if err != nil {
		return fmt.Errorf("failed to get root, %s", err)
	}

	rootDisk, err := s.service.GetRootDisk(ctx)
	if err != nil {
		return fmt.Errorf("failed to get root disk, %s", err)
	}

	rootPartNum, err := s.service.GetRootPartNumber(ctx, root)
	if err != nil {
		return fmt.Errorf("failed to get root part number, %s", err)
	}

	for _, rootPart := range info.GetMiniOSPartitions() {
		if isSupported, err := s.service.IsMiniOSPartitionSupported(ctx, rootDisk, rootPart); err == nil && !isSupported {
			log.Printf("device does not support MiniOS, skipping installation.")
			return nil
		} else if err != nil {
			return fmt.Errorf("failed to determine miniOS suport, %s", err)
		}
	}

	s.service.InstallMiniOS(ctx, info.GetPartitionInfo(root, rootDisk, rootPartNum))
	return nil

}

func (s CrOSInstallMiniOSState) Next() services.ServiceState {
	return nil
}

func (s CrOSInstallMiniOSState) Name() string {
	return "CrOS Install MiniOS"
}
