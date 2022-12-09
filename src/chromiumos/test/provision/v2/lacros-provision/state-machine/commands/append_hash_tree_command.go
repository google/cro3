// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// Append the hashtree (merkle tree) onto the end of the Lacros image.
package commands

import (
	"chromiumos/test/provision/v2/lacros-provision/service"
	"context"
	"fmt"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type AppendHashTreeCommand struct {
	ctx context.Context
	cs  *service.LaCrOSService
}

func NewAppendHashTreeCommand(ctx context.Context, cs *service.LaCrOSService) *AppendHashTreeCommand {
	return &AppendHashTreeCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *AppendHashTreeCommand) Execute(log *log.Logger) error {
	if _, err := c.cs.Connection.RunCmd(c.ctx, "cat", []string{
		c.cs.GetHashTreePath(),
		">>",
		c.cs.GetLocalImagePath(),
	}); err != nil {
		return fmt.Errorf("failed to append hashtree to Lacros image, %w", err)
	}
	return nil
}

func (c *AppendHashTreeCommand) Revert() error {
	return nil
}

func (c *AppendHashTreeCommand) GetErrorMessage() string {
	return "failed to append hash tree"
}

func (c *AppendHashTreeCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_UPDATE_FIRMWARE_FAILED
}
