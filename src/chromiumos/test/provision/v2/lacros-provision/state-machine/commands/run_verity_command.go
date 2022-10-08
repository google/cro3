// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// RunVerity generates the verity (hashtree and table) from Lacros image.
package commands

import (
	"chromiumos/test/provision/v2/lacros-provision/service"
	"context"
	"fmt"
	"log"
)

type RunVerityCommand struct {
	ctx context.Context
	cs  *service.LaCrOSService
}

func NewRunVerityCommand(ctx context.Context, cs *service.LaCrOSService) *RunVerityCommand {
	return &RunVerityCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *RunVerityCommand) Execute(log *log.Logger) error {
	// Generate the verity (hashtree and table) from Lacros image.
	if _, err := c.cs.Connection.RunCmd(c.ctx, "verity", []string{
		"mode=create",
		"alg=sha256",
		fmt.Sprintf("payload=%s", c.cs.GetLocalImagePath()),
		fmt.Sprintf("payload_blocks=%d", c.cs.Blocks),
		fmt.Sprintf("hashtree=%s", c.cs.GetHashTreePath()),
		"salt=random",
		">",
		c.cs.GetTablePath(),
	}); err != nil {
		return fmt.Errorf("failed to generate verity for Lacros image, %w", err)
	}
	return nil
}

func (c *RunVerityCommand) Revert() error {
	return nil
}

func (c *RunVerityCommand) GetErrorMessage() string {
	return "failed to run verity"
}
