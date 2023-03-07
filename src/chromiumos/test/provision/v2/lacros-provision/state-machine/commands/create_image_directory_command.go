// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// CreateImageDirectory downloads the metadata file locally
package commands

import (
	"chromiumos/test/provision/v2/lacros-provision/service"
	"context"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type CreateImageDirectoryCommand struct {
	ctx context.Context
	cs  *service.LaCrOSService
}

func NewCreateImageDirectoryCommand(ctx context.Context, cs *service.LaCrOSService) *CreateImageDirectoryCommand {
	return &CreateImageDirectoryCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *CreateImageDirectoryCommand) Execute(log *log.Logger) error {
	return c.cs.Connection.CreateDirectories(c.ctx, []string{c.cs.GetComponentPath()})
}

func (c *CreateImageDirectoryCommand) Revert() error {
	return nil
}

func (c *CreateImageDirectoryCommand) GetErrorMessage() string {
	return "failed to create local image directory"
}

func (c *CreateImageDirectoryCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_UPDATE_FIRMWARE_FAILED
}