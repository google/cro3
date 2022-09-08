// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// CopyImage downloads the metadata file locally
package commands

import (
	"chromiumos/test/provision/v2/ash-provision/service"
	"context"
	"fmt"

	conf "go.chromium.org/chromiumos/config/go"
)

type CopyImageCommand struct {
	ctx context.Context
	cs  *service.AShService
}

func NewCopyImageCommand(ctx context.Context, cs *service.AShService) *CopyImageCommand {
	return &CopyImageCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *CopyImageCommand) Execute() error {
	switch c.cs.ImagePath.HostType {
	case conf.StoragePath_GS:
		return c.cs.Connection.PipeData(c.ctx, c.cs.ImagePath.GetPath(), fmt.Sprintf("tar --ignore-command-error --overwrite --preserve-permissions --directory=%s -xf -", c.cs.GetStagingDirectory()))
	default:
		return fmt.Errorf("only GS copying is implemented")
	}
}

func (c *CopyImageCommand) Revert() error {
	return nil
}

func (c *CopyImageCommand) GetErrorMessage() string {
	return "failed to copy image"
}
