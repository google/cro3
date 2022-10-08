// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/ash-provision/service"
	"context"
	"log"
)

type CreateNewStagingDirsCommand struct {
	ctx context.Context
	cs  *service.AShService
}

func NewCreateNewStagingDirsCommand(ctx context.Context, cs *service.AShService) *CreateNewStagingDirsCommand {
	return &CreateNewStagingDirsCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *CreateNewStagingDirsCommand) Execute(log *log.Logger) error {
	return c.cs.Connection.CreateDirectories(c.ctx, []string{c.cs.GetStagingDirectory()})
}

func (c *CreateNewStagingDirsCommand) Revert() error {
	return nil
}

func (c *CreateNewStagingDirsCommand) GetErrorMessage() string {
	return "failed to create new staging directories"
}
