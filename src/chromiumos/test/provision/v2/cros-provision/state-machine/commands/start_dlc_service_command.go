// Copyright 2022 The ChromiumOS Authors.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"log"
)

type StartDLCServiceCommand struct {
	ctx context.Context
	cs  service.CrOSService
}

func NewStartDLCServiceCommand(ctx context.Context, cs service.CrOSService) *StartDLCServiceCommand {
	return &StartDLCServiceCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *StartDLCServiceCommand) Execute() error {
	if _, err := c.cs.Connection.RunCmd(c.ctx, "start", []string{"dlcservice"}); err != nil {
		log.Printf("%s, %s", c.GetErrorMessage(), err)
	}
	return nil
}

func (c *StartDLCServiceCommand) Revert() error {
	return nil
}

func (c *StartDLCServiceCommand) GetErrorMessage() string {
	return "failed to start DLC service"
}
