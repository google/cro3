// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"fmt"
	"log"
	"path"
)

type ClearDLCArtifactsCommand struct {
	ctx context.Context
	cs  service.CrOSService
}

func NewClearDLCArtifactsCommand(ctx context.Context, cs service.CrOSService) *ClearDLCArtifactsCommand {
	return &ClearDLCArtifactsCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *ClearDLCArtifactsCommand) Execute() error {
	exists, err := c.cs.Connection.PathExists(c.ctx, common_utils.DlcLibDir)
	if err != nil {
		return fmt.Errorf("failed path existance, %s", err)
	}
	if !exists {
		return fmt.Errorf("DLC path does not exist")
	}

	// Stop dlcservice daemon in order to not interfere with clearing inactive verified DLCs.
	if _, err := c.cs.Connection.RunCmd(c.ctx, "stop", []string{"dlcservice"}); err != nil {
		log.Printf("failed to stop dlcservice daemon, %s", err)
	}
	defer func() {
		if _, err := c.cs.Connection.RunCmd(c.ctx, "start", []string{"dlcservice"}); err != nil {
			log.Printf("failed to start dlcservice daemon, %s", err)
		}
	}()

	inactiveSlot := common_utils.InactiveDlcMap[c.cs.MachineMetadata.RootInfo.RootPartNum]
	if inactiveSlot == "" {
		return fmt.Errorf("invalid root partition number: %s", c.cs.MachineMetadata.RootInfo.RootPartNum)
	}
	_, err = c.cs.Connection.RunCmd(c.ctx, "rm", []string{"-f", path.Join(common_utils.DlcCacheDir, "*", "*", string(inactiveSlot), common_utils.DlcVerified)})
	if err != nil {
		return fmt.Errorf("failed remove inactive verified DLCs, %s", err)
	}

	return nil
}

func (c *ClearDLCArtifactsCommand) Revert() error {
	return nil
}

func (c *ClearDLCArtifactsCommand) GetErrorMessage() string {
	return "Failed to clear DLC artifacts"
}
