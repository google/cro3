// Copyright 2021 The Chromium OS Authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package lacrosservice

import (
	"chromiumos/test/provision/cmd/provisionserver/bootstrap/services"
	"context"
	"fmt"
)

// First step of LaCrOSInstall State Machine. Responsible for partition and install
type LaCrOSInstallState struct {
	service LaCrOSService
}

// Execute will download and install the Lacros image into the imageloader
// component directory with the version from the metadata.json file.
// The Lacros image will also be modified with the correct verity output.
func (s LaCrOSInstallState) Execute(ctx context.Context) error {
	if err := s.service.CopyImageToDUT(ctx); err != nil {
		return fmt.Errorf("failed to copy image to server %w", err)
	}
	payloadBlocks, err := s.service.AlignImageToPage(ctx)
	if err != nil {
		return fmt.Errorf("failed to align image to page, %w", err)
	}
	if err := s.service.RunVerity(ctx, payloadBlocks); err != nil {
		return fmt.Errorf("failed to run verity, %w", err)
	}
	if err := s.service.AppendHashtree(ctx); err != nil {
		return fmt.Errorf("failed to append to hash tree, %w", err)
	}
	return nil
}

func (s LaCrOSInstallState) Next() services.ServiceState {
	return LaCrOSPostInstallState{
		service: s.service,
	}
}

func (s LaCrOSInstallState) Name() string {
	return "LaCrOS Install"
}
