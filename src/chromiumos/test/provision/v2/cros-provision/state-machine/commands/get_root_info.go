// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/common-utils/metadata"
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"fmt"
	"regexp"
	"strings"
)

type GetRootInfoCommand struct {
	ctx context.Context
	cs  service.CrOSService
}

func NewGetRootInfoCommand(ctx context.Context, cs service.CrOSService) *GetRootInfoCommand {
	return &GetRootInfoCommand{
		ctx: ctx,
		cs:  cs,
	}

}

func (c *GetRootInfoCommand) Execute() error {
	root, err := c.getRoot()
	if err != nil {
		return fmt.Errorf("failed to get root, %s", err)
	}
	rootDisk, err := c.getRootDisk()
	if err != nil {
		return fmt.Errorf("failed to get root disk, %s", err)
	}
	rootPartNum, err := c.getRootPartNumber(root)
	if err != nil {
		return fmt.Errorf("failed to get root part number, %s", err)
	}

	pi := common_utils.GetPartitionInfo(root, rootDisk, rootPartNum)

	c.cs.MachineMetadata.RootInfo = metadata.RootInfo{
		Root:          root,
		RootDisk:      rootDisk,
		RootPartNum:   rootPartNum,
		PartitionInfo: pi,
	}

	return nil
}

func (c *GetRootInfoCommand) Revert() error {
	// Thought this method has side effects to the service it does not to the OS,
	// as such Revert here is unneded
	return nil
}

// GetRoot returns the rootdev outoput for root
func (c *GetRootInfoCommand) getRoot() (string, error) {
	// Example 1: "/dev/nvme0n1p3"
	// Example 2: "/dev/sda3"
	curRoot, err := c.cs.Connection.RunCmd(c.ctx, "rootdev", []string{"-s"})
	if err != nil {
		return "", fmt.Errorf("failed to get current root, %s", err)
	}
	return strings.TrimSpace(curRoot), nil
}

// GetRootDisk returns the rootdev output for disk
func (c *GetRootInfoCommand) getRootDisk() (string, error) {
	// Example 1: "/dev/nvme0n1"
	// Example 2: "/dev/sda"
	rootDisk, err := c.cs.Connection.RunCmd(c.ctx, "rootdev", []string{"-s", "-d"})
	if err != nil {
		return "", fmt.Errorf("failed to get root disk, %s", err)
	}
	return strings.TrimSpace(rootDisk), nil
}

// GetRootPartNumber parses the root number for a specific root
func (c *GetRootInfoCommand) getRootPartNumber(root string) (string, error) {
	// Handle /dev/mmcblk0pX, /dev/sdaX, etc style partitions.
	// Example 1: "3"
	// Example 2: "3"
	match := regexp.MustCompile(`.*([0-9]+)`).FindStringSubmatch(root)
	if match == nil {
		return "", fmt.Errorf("failed to match partition number from %s", root)
	}

	switch match[1] {
	case common_utils.PartitionNumRootA, common_utils.PartitionNumRootB:
		break
	default:
		return "", fmt.Errorf("invalid partition number %s", match[1])
	}

	return match[1], nil
}

func (c *GetRootInfoCommand) GetErrorMessage() string {
	return "failed to get root info"
}
