// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/cros-provision/service"
	"context"
	"log"
)

type StopSystemDaemonsCommand struct {
	ctx context.Context
	cs  *service.CrOSService
}

func NewStopSystemDaemonsCommand(ctx context.Context, cs *service.CrOSService) *StopSystemDaemonsCommand {
	return &StopSystemDaemonsCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *StopSystemDaemonsCommand) Execute() error {
	if _, err := c.cs.Connection.RunCmd(c.ctx, "stop", []string{"ui"}); err != nil {
		log.Printf("Failed to stop UI daemon, %s", err)
	}
	if _, err := c.cs.Connection.RunCmd(c.ctx, "stop", []string{"update-engine"}); err != nil {
		log.Printf("Failed to stop update-engine daemon, %s", err)
	}
	return nil
}

func (c *StopSystemDaemonsCommand) Revert() error {
	return nil
}

func (c *StopSystemDaemonsCommand) GetErrorMessage() string {
	return "failed to stop system daemons"
}
