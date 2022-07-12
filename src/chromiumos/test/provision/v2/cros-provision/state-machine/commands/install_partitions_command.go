// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"fmt"
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

func (c *InstallPartitionsCommand) Execute() error {

	if err := c.cs.InstallZippedImage(c.ctx, "full_dev_part_KERN.bin.gz", c.cs.MachineMetadata.RootInfo.PartitionInfo.InactiveKernel); err != nil {
		return fmt.Errorf("install kernel: %s", err)
	}
	if err := c.cs.InstallZippedImage(c.ctx, "full_dev_part_ROOT.bin.gz", c.cs.MachineMetadata.RootInfo.PartitionInfo.InactiveRoot); err != nil {
		return fmt.Errorf("install root: %s", err)
	}

	return nil
}

func (c *InstallPartitionsCommand) Revert() error {
	return nil
}

func (c *InstallPartitionsCommand) GetErrorMessage() string {
	return "failed to install partitions"
}
