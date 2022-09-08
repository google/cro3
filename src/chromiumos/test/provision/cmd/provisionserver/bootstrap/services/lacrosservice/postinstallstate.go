// Copyright 2021 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package lacrosservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
)

// Second step of LaCrOSInstall State Machine. Responsible for stateful provisioning
type LaCrOSPostInstallState struct {
	service LaCrOSService
}

func (s LaCrOSPostInstallState) Execute(ctx context.Context) error {
	if err := s.service.writeManifest(ctx); err != nil {
		return fmt.Errorf("failed to write LaCrOS manifest, %w", err)
	}
	if err := s.service.writeComponentManifest(ctx); err != nil {
		return fmt.Errorf("failed to write LaCrOS component manifest, %w", err)
	}
	if err := s.service.PublishVersion(ctx); err != nil {
		return fmt.Errorf("failed to publish version, %w", err)
	}
	if err := s.service.FixOwnership(ctx); err != nil {
		return fmt.Errorf("failed to fix ownership, %w", err)
	}
	return nil
}

func (s LaCrOSPostInstallState) Next() services.ServiceState {
	return LaCrOSVerifyState{
		service: s.service,
	}
}

func (s LaCrOSPostInstallState) Name() string {
	return "LaCrOS Post Install"
}
