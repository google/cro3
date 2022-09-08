// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"log"
)

type StopDLCServiceCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewStopDLCServiceCommand(ctx context.Context, cs *service.CrOSService) *StopDLCServiceCommand {
	return &StopDLCServiceCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *StopDLCServiceCommand) Execute() error {
	if _, err := c.cs.Connection.RunCmd(c.ctx, "stop", []string{"dlcservice"}); err != nil {
		log.Printf("%s, %s", c.GetErrorMessage(), err)
	}
	return nil
}

func (c *StopDLCServiceCommand) Revert() error {
	return nil
}

func (c *StopDLCServiceCommand) GetErrorMessage() string {
	return "failed to stop DLC service"
}
