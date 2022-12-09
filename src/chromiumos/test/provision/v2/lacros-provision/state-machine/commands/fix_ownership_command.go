// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// FixOwnership changes file mode and owner of provisioned files if the path is
// prefixed with the CrOS component path.
package commands

import (
	"chromiumos/test/provision/v2/lacros-provision/service"
	"context"
	"fmt"
	"log"
	"strings"

	"go.chromium.org/chromiumos/config/go/test/api"
)

type FixOwnershipCommand struct {
	ctx context.Context
	cs  *service.LaCrOSService
}

func NewFixOwnershipCommand(ctx context.Context, cs *service.LaCrOSService) *FixOwnershipCommand {
	return &FixOwnershipCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *FixOwnershipCommand) Execute(log *log.Logger) error {
	if strings.HasPrefix(c.cs.GetComponentPath(), c.cs.GetComponentRootPath()) {
		if _, err := c.cs.Connection.RunCmd(c.ctx, "chown", []string{"-R", "chronos:chronos", c.cs.GetComponentRootPath()}); err != nil {
			return fmt.Errorf("could not change component path ownership for %s, %s", c.cs.GetComponentRootPath(), err)
		}
		if _, err := c.cs.Connection.RunCmd(c.ctx, "chmod", []string{"-R", "0755", c.cs.GetComponentRootPath()}); err != nil {
			return fmt.Errorf("could not change component path permissions for %s, %s", c.cs.GetComponentRootPath(), err)

		}
	}
	return nil
}

func (c *FixOwnershipCommand) Revert() error {
	return nil
}

func (c *FixOwnershipCommand) GetErrorMessage() string {
	return "failed to fix ownership"
}

func (c *FixOwnershipCommand) GetStatus() api.InstallResponse_Status {
	return api.InstallResponse_STATUS_UPDATE_FIRMWARE_FAILED
}
