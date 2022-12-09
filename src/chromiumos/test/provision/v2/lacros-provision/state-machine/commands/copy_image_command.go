// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// CopyImage downloads the metadata file locally
package commands

import (
	"chromiumos/test/provision/v2/lacros-provision/service"
	"context"
	"fmt"
	"log"

	conf "go.chromium.org/chromiumos/config/go"
	"go.chromium.org/chromiumos/config/go/test/api"
)

type CopyImageCommand struct {
	ctx context.Context
	cs  *service.LaCrOSService
}

func NewCopyImageCommand(ctx context.Context, cs *service.LaCrOSService) *CopyImageCommand {
	return &CopyImageCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *CopyImageCommand) Execute(log *log.Logger) error {
	switch c.cs.ImagePath.HostType {
	case conf.StoragePath_GS:
		if err := c.cs.Connection.CopyData(c.ctx, c.cs.GetCompressedImagePath(), c.cs.GetLocalImagePath()); err != nil {
			return err
		}
	case conf.StoragePath_LOCAL:
		if _, err := c.cs.Connection.RunCmd(c.ctx, "cp", []string{c.cs.GetDeviceCompressedImagePath(), c.cs.GetLocalImagePath()}); err != nil {
			return err
		}
	default:
		return fmt.Errorf("only GS and LOCAL copying are implemented")
	}
	return nil
}

func (c *CopyImageCommand) Revert() error {
	return nil
}

func (c *CopyImageCommand) GetErrorMessage() string {
	return "failed to copy image"
}

func (c *CopyImageCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_UPDATE_FIRMWARE_FAILED
}
