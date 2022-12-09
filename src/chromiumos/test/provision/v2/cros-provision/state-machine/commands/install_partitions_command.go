// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"fmt"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type InstallPartitionsCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewInstallPartitionsCommand(ctx context.Context, cs *service.CrOSService) *InstallPartitionsCommand {
	return &InstallPartitionsCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *InstallPartitionsCommand) Execute(log *log.Logger) error {
	log.Printf("Start InstallPartitionsCommand Execute")

	if err := c.cs.InstallZippedImage(c.ctx, "full_dev_part_KERN.bin.gz", c.cs.MachineMetadata.RootInfo.PartitionInfo.InactiveKernel); err != nil {
		return fmt.Errorf("install kernel: %s", err)
	}
	log.Printf("InstallPartitionsCommand full_dev_part_KERN COMPLETED")

	if err := c.cs.InstallZippedImage(c.ctx, "full_dev_part_ROOT.bin.gz", c.cs.MachineMetadata.RootInfo.PartitionInfo.InactiveRoot); err != nil {
		return fmt.Errorf("install root: %s", err)
	}
	log.Printf("InstallPartitionsCommand full_dev_part_ROOT COMPLETED")
	log.Printf("InstallPartitionsCommand Success")

	return nil
}

func (c *InstallPartitionsCommand) Revert() error {
	return nil
}

func (c *InstallPartitionsCommand) GetErrorMessage() string {
	return "failed to install partitions"
}

func (c *InstallPartitionsCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_DOWNLOADING_IMAGE_FAILED
}
