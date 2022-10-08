// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// CopyMetadata downloads the metadata file locally
package commands

import (
	"chromiumos/test/provision/v2/lacros-provision/service"
	"context"
	"fmt"
	"log"

	conf "go.chromium.org/chromiumos/config/go"
)

type CopyMetadataCommand struct {
	ctx context.Context
	cs  *service.LaCrOSService
}

func NewCopyMetadataCommand(ctx context.Context, cs *service.LaCrOSService) *CopyMetadataCommand {
	return &CopyMetadataCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *CopyMetadataCommand) Execute(log *log.Logger) error {
	switch c.cs.ImagePath.HostType {
	case conf.StoragePath_GS:
		if err := c.cs.Connection.CopyData(c.ctx, c.cs.GetMetatadaPath(), "/tmp/metadata.json"); err != nil {
			return err
		}
	case conf.StoragePath_LOCAL:
		if _, err := c.cs.Connection.RunCmd(c.ctx, "cp", []string{c.cs.GetMetatadaPath(), "/tmp/metadata.json"}); err != nil {
			return err
		}
	default:
		return fmt.Errorf("only GS and LOCAL copying are implemented")
	}
	return nil
}

func (c *CopyMetadataCommand) Revert() error {
	return nil
}

func (c *CopyMetadataCommand) GetErrorMessage() string {
	return "failed to copy metadata"
}
