// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

// ReloadBus kill the bus daemon with a SIGHUP
package commands

import (
	"chromiumos/test/provision/v2/ash-provision/service"
	"context"
)

type ReloadBusCommand struct {
	ctx context.Context
	cs  *service.AShService
}

func NewReloadBusCommand(ctx context.Context, cs *service.AShService) *ReloadBusCommand {
	return &ReloadBusCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *ReloadBusCommand) Execute() error {
	if _, err := c.cs.Connection.RunCmd(c.ctx, "killall", []string{"-HUP", "dbus-daemon"}); err != nil {
		return err
	}
	return nil
}

func (c *ReloadBusCommand) Revert() error {
	return nil
}

func (c *ReloadBusCommand) GetErrorMessage() string {
	return "failed to reload bus"
}
