// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// PublishVersion writes the Lacros version to the latest-version file.
package commands

import (
	"chromiumos/test/provision/v2/lacros-provision/service"
	"context"
	"log"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type PublishVersionCommand struct {
	ctx context.Context
	cs  *service.LaCrOSService
}

func NewPublishVersionCommand(ctx context.Context, cs *service.LaCrOSService) *PublishVersionCommand {
	return &PublishVersionCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *PublishVersionCommand) Execute(log *log.Logger) error {
	return c.cs.WriteToFile(c.ctx, c.cs.LaCrOSMetadata.Content.Version, c.cs.GetLatestVersionPath())
}

func (c *PublishVersionCommand) Revert() error {
	return nil
}

func (c *PublishVersionCommand) GetErrorMessage() string {
	return "failed to publish version"
}

func (c *PublishVersionCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_UPDATE_FIRMWARE_FAILED
}
