// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/ash-provision/service"
	"context"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type CleanUpStagingCommand struct {
	ctx context.Context
	cs  *service.AShService
}

func NewCleanUpStagingCommand(ctx context.Context, cs *service.AShService) *CleanUpStagingCommand {
	return &CleanUpStagingCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *CleanUpStagingCommand) Execute(log *log.Logger) error {
	return c.cs.Connection.DeleteDirectory(c.ctx, c.cs.GetStagingDirectory())
}

func (c *CleanUpStagingCommand) Revert() error {
	return nil
}

func (c *CleanUpStagingCommand) GetErrorMessage() string {
	return "failed to clean up staging directory"
}

func (c *CleanUpStagingCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_PROVISIONING_FAILED
}
