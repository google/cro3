// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package ashservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
)

// Third step of AshInstall State Machine. Responsible for general clean-up
type AshPostInstallState struct {
	service AshService
}

func (s AshPostInstallState) Execute(ctx context.Context) error {
	if err := s.service.ReloadBus(ctx); err != nil {
		return fmt.Errorf("could not reload bus, %w", err)
	}
	if err := s.service.StartChrome(ctx); err != nil {
		return fmt.Errorf("could not start UI, %w", err)
	}
	if err := s.service.CleanUpStagingDirectory(ctx); err != nil {
		return fmt.Errorf("could not delete staging directory, %w", err)
	}
	return nil
}

func (s AshPostInstallState) Next() services.ServiceState {
	return nil
}

func (s AshPostInstallState) Name() string {
	return "Ash PostInstall"
}
