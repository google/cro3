// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// First step of CrOSInstall State Machine. Responsible for partition and install
package crosservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/info"
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
)

type CrOSInstallState struct {
	service CrOSService
}

func (s CrOSInstallState) Execute(ctx context.Context) error {
	if err := s.service.CreateProvisionMarker(ctx); err != nil {
		return fmt.Errorf("failed to create provision marker, %s", err)
	}

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
	s.service.StopSystemDaemons(ctx)
	if err := s.service.ClearDLCArtifacts(ctx, rootPartNum); err != nil {
		return fmt.Errorf("failed to clear DLC artifacts, %s", err)
	}
	pi := info.GetPartitionInfo(root, rootDisk, rootPartNum)
	if err := s.service.InstallPartitions(ctx, pi); err != nil {
		return fmt.Errorf("failed to provision the OS, %s", err)
	}
	if err := s.service.PostInstall(ctx, pi.InactiveRoot); err != nil {
		s.service.RevertProvisionOS(ctx, pi.ActiveRoot)
		return fmt.Errorf("failed to set next kernel, %s", err)
	}
	if s.service.CanClearTPM(ctx) {
		if err := s.service.ClearTPM(ctx); err != nil {
			s.service.RevertProvisionOS(ctx, pi.ActiveRoot)
			return fmt.Errorf("failed to clear TPM, %s", err)
		}
	}

	return nil
}

func (s CrOSInstallState) Next() services.ServiceState {
	return CrOSPostInstallState{
		service: s.service,
	}
}

func (s CrOSInstallState) Name() string {
	return "CrOS Install"
}