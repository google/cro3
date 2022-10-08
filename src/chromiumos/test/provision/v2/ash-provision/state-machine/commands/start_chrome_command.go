// Copyright 2022 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package commands

import (
	"chromiumos/test/provision/v2/ash-provision/service"
	"context"
	"log"
)

type StartChromeCommand struct {
	ctx context.Context
	cs  *service.AShService
}

func NewStartChromeCommand(ctx context.Context, cs *service.AShService) *StartChromeCommand {
	return &StartChromeCommand{
		ctx: ctx,
		cs:  cs,
	}
}

func (c *StartChromeCommand) Execute(log *log.Logger) error {
	if _, err := c.cs.Connection.RunCmd(c.ctx, "start", []string{"ui"}); err != nil {
		return err
	}
	return nil
}

func (c *StartChromeCommand) Revert() error {
	return nil
}

func (c *StartChromeCommand) GetErrorMessage() string {
	return "failed to start chrome"
}
