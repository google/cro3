// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ashservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
)

// First step of AshInstall State Machine. Responsible for preparing the machine for the installation
type AshPrepareState struct {
	service AshService
}

func (s AshPrepareState) Execute(ctx context.Context) error {
	if err := s.service.CreateStagingDirectory(ctx); err != nil {
		return fmt.Errorf("could not recreate staging directory, %w", err)
	}
	if err := s.service.CopyImageToDUT(ctx); err != nil {
		return fmt.Errorf("could not copy image to DUT, %w", err)
	}
	if err := s.service.CreateBinaryDirectories(ctx); err != nil {
		return fmt.Errorf("could not create target directories, %w", err)
	}
	if err := s.service.StopChrome(ctx); err != nil {
		return fmt.Errorf("could not stop chrome, %w", err)
	}
	if err := s.service.KillChrome(ctx); err != nil {
		return fmt.Errorf("could not kill chrome, %w", err)
	}
	return nil
}

func (s AshPrepareState) Next() services.ServiceState {
	return AshInstallState{
		service: s.service,
	}
}

func (s AshPrepareState) Name() string {
	return "Ash Prepare"
}
