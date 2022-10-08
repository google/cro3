// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"fmt"
	"log"
	"strings"
)

type InstallMiniOSCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewInstallMiniOSCommand(ctx context.Context, cs *service.CrOSService) *InstallMiniOSCommand {
	return &InstallMiniOSCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *InstallMiniOSCommand) Execute(log *log.Logger) error {
	log.Printf("Start InstallMiniOSCommand Execute")
	for _, rootPart := range common_utils.GetMiniOSPartitions() {
		if isSupported, err := c.isMiniOSPartitionSupported(rootPart); err == nil && !isSupported {
			log.Printf("InstallMiniOSCommand device does not support MiniOS, skipping installation.")
			return nil
		} else if err != nil {
			return fmt.Errorf("failed to determine miniOS suport, %s", err)
		}
	}
	log.Printf("InstallMiniOSCommand Running Install")

	return c.installMiniOS(log)
}

func (c *InstallMiniOSCommand) Revert() error {
	return nil
}

// IsMiniOSPartitionSupported determines whether the device has the partitions
func (c *InstallMiniOSCommand) isMiniOSPartitionSupported(rootPart string) (bool, error) {
	guidPartition, err := c.cs.Connection.RunCmd(c.ctx, "cgpt", []string{"show", "-t", c.cs.MachineMetadata.RootInfo.RootDisk, "-i", rootPart})
	if err != nil {
		return false, fmt.Errorf("failed to get partition type, %s\n %s", err, guidPartition)
	}

	return strings.TrimSpace(guidPartition) == common_utils.MiniOSUnsupportedGUIDPartition, nil
}

// InstallMiniOS downloads and installs the minios images
func (c *InstallMiniOSCommand) installMiniOS(log *log.Logger) error {
	if err := c.cs.InstallZippedImage(c.ctx, "full_dev_part_MINIOS.bin.gz", c.cs.MachineMetadata.RootInfo.PartitionInfo.MiniOSA); err != nil {
		return fmt.Errorf("install MiniOS A: %s", err)
	}
	log.Printf("InstallMiniOSCommand installed full_dev_part_MINIOS MiniOSA")
	if err := c.cs.InstallZippedImage(c.ctx, "full_dev_part_MINIOS.bin.gz", c.cs.MachineMetadata.RootInfo.PartitionInfo.MiniOSB); err != nil {
		return fmt.Errorf("install MiniOS B: %s", err)
	}
	log.Printf("InstallMiniOSCommand installed full_dev_part_MINIOS MiniOSB")
	log.Printf("InstallMiniOSCommand Success")
	return nil
}

func (c *InstallMiniOSCommand) GetErrorMessage() string {
	return "failed to install MiniOS"
}
