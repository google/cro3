// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	common_utils "chromiumos/test/provision/v2/common-utils"
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
)

type CreateProvisionMarkerCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewCreateProvisionMarkerCommand(ctx context.Context, cs *service.CrOSService) *CreateProvisionMarkerCommand {
	return &CreateProvisionMarkerCommand{
		ctx: ctx,
		cs:  cs,
	}

}

func (c *CreateProvisionMarkerCommand) Execute() error {
	if _, err := c.cs.Connection.RunCmd(c.ctx, "touch", []string{common_utils.ProvisionMarker}); err != nil {
		return err
	}
	return nil
}

func (c *CreateProvisionMarkerCommand) Revert() error {
	return nil
}

func (c *CreateProvisionMarkerCommand) GetErrorMessage() string {
	return "failed to create provision marker"
}
