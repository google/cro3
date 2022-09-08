// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ashservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
)

// Second step of AshInstall State Machine. Responsible for installation
type AshInstallState struct {
	service AshService
}

func (s AshInstallState) Execute(ctx context.Context) error {
	if err := s.service.MountRootFS(ctx); err != nil {
		return fmt.Errorf("could not mount root file system, %w", err)
	}
	if err := s.service.Deploy(ctx); err != nil {
		return fmt.Errorf("could not deploy ash files, %w", err)
	}
	return nil
}

func (s AshInstallState) Next() services.ServiceState {
	return AshPostInstallState{
		service: s.service,
	}
}

func (s AshInstallState) Name() string {
	return "Ash Install"
}
